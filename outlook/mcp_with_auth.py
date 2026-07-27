import requests
import json
from fastmcp import FastMCP
from fastmcp.server.auth.providers.azure import AzureProvider, EntraOBOToken
from fastmcp.server.dependencies import get_access_token
from datetime import datetime, timedelta, timezone
import httpx
import os
import dotenv
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

#dotenv.load_dotenv(dotenv_path=".env", override=True)

auth_provider = AzureProvider(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    tenant_id=os.getenv("TENANT_ID"),
    base_url=os.getenv("BASE_URL"),
    required_scopes=["read"],
    additional_authorize_scopes=[
        "https://graph.microsoft.com/Calendars.ReadWrite",  # 請求行事曆讀寫權限
        "https://graph.microsoft.com/User.Read"            # 讀取使用者基本資料
    ]
)


mcp = FastMCP("Outlook MCP", auth=auth_provider)
@mcp.tool
async def get_user_info() -> dict: 
    try:
        token = get_access_token()
        if not token:
            return {"error": "No token provided"}
        token_dict = json.loads(token.model_dump_json())
        email = token_dict.get('claims').get('preferred_username')
        name = token_dict.get('claims').get('name') 
        return  {"name": name, "email": email} 
    except Exception as e:
        print(f"DEBUG: Auth Error Details: {str(e)}")
        return {"error": str(e)}

@mcp.tool
async def get_user_calendar_events(
    start_iso, end_iso,
    time_range: str = "week",
    graph_token: str = EntraOBOToken(["https://graph.microsoft.com/Calendars.Read"]),
) -> dict:
    """Get the user's calendar events from Microsoft Graph.

    Args:
        start_iso: Started time  which is formatted by YYYY-MM-DD
        end_iso: End time which is formatted by YYYY-MM-DD
        graph_token: OAuth token for Microsoft Graph
    """
    try:
        def clean_text(text):
            return text.replace('\n', ' ').replace('\r', ' ').replace('_', '').strip()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/calendarview?startDateTime={start_iso}&endDateTime={end_iso}",
                headers={"Authorization": f"Bearer {graph_token}"},
            )
            response.raise_for_status()
            data = response.json()

        events = data.get('value', [])
        print(events)
        formatted_events = [
            {
                "subject": event.get('subject', 'No Subject'),
                "start": datetime.strptime(event.get('start', {}).get('dateTime', '')[:19], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=8) if event.get('start', {}).get('dateTime') else 'No Start Time',
                "end": datetime.strptime(event.get('end', {}).get('dateTime', '')[:19], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=8) if event.get('end', {}).get('dateTime') else 'No End Time',
                "location": event.get('location', {}).get('displayName', 'No Location'),
                "bodyPreview": clean_text(event.get('bodyPreview', 'No Preview')),
                "webLink": event.get('webLink', 'No Link'),
                "attendees": [att.get('emailAddress', {}).get('address', 'Unknown') for att in event.get('attendees', [])],
            }
            for event in events
        ]
        return {
            "time_range": time_range,
            "event_count": len(formatted_events),
            "events": formatted_events
        }
    except Exception as e:
        print(f"DEBUG: Fetch Calendar Failed: {str(e)}")
        return {"error": str(e)}

@mcp.tool
async def get_free_busy_calendar_events(
    attendee_email: list[str],
    start_time: str,
    end_time: str,
    location: str = None,
    graph_token: str = EntraOBOToken(["https://graph.microsoft.com/Calendars.Read"]),
) -> dict:
    """Find available meeting times for attendees.

    Args:
        attendee_email: List of attendee emails
        start_time: Start time for search (ISO format, e.g., 2026-07-28T09:00:00)
        end_time: End time for search (ISO format, e.g., 2026-07-28T18:00:00)
        location: Optional location constraint for the meeting
        graph_token: OAuth token for Microsoft Graph
    """
    try:
        body = {
            "attendees": [{"emailAddress": {"address": email}} for email in attendee_email],
            "timeConstraint": {
                "timeSlots": [
                    {
                        "start": {"dateTime": start_time, "timeZone": "Asia/Taipei"},
                        "end": {"dateTime": end_time, "timeZone": "Asia/Taipei"}
                    }
                ]
            },
            "minimumAttendeePercentage": 100
        }

        if location:
            body["locationConstraint"] = {
                "locations": [{"displayName": location}],
                "resolveAvailability": False
            }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://graph.microsoft.com/v1.0/me/findMeetingTimes",
                headers={"Authorization": f"Bearer {graph_token}"},
                json=body
            )
            response.raise_for_status()
            data = response.json()

        meeting_suggestions = data.get("meetingTimeSuggestions", [])
        formatted_suggestions = []

        for suggestion in meeting_suggestions:
            start_str = suggestion["meetingTimeSlot"]["start"]["dateTime"]
            end_str = suggestion["meetingTimeSlot"]["end"]["dateTime"]

            start_dt = datetime.strptime(start_str[:19], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=8)
            end_dt = datetime.strptime(end_str[:19], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=8)

            formatted_suggestions.append({
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "confidence": suggestion.get("confidence", 0),
                "attendeeAvailability": suggestion.get("attendeeAvailability", [])
            })

        return {
            "meeting_times": formatted_suggestions,
            "status": "success"
        }
    except Exception as e:
        print(f"DEBUG: Find Meeting Times Failed: {str(e)}")
        return {"error": str(e)}

@mcp.tool
async def create_calendar_event(
    subject: str,
    start_time: str,
    end_time: str,
    attendee_emails: list[str] = None,
    location: str = None,
    description: str = None,
    graph_token: str = EntraOBOToken(["https://graph.microsoft.com/Calendars.ReadWrite"]),
) -> dict:
    """Create a new calendar event.

    Args:
        subject: Event title
        start_time: Start time (ISO format, e.g., 2026-07-28T14:00:00)
        end_time: End time (ISO format, e.g., 2026-07-28T15:00:00)
        attendee_emails: List of attendee email addresses (optional)
        location: Event location (optional)
        description: Event description (optional)
        graph_token: OAuth token for Microsoft Graph (requires Calendars.ReadWrite scope)
    """
    try:
        body = {
            "subject": subject,
            "start": {
                "dateTime": start_time,
                "timeZone": "Asia/Taipei"
            },
            "end": {
                "dateTime": end_time,
                "timeZone": "Asia/Taipei"
            }
        }

        if location:
            body["location"] = {"displayName": location}

        if description:
            body["bodyPreview"] = description

        if attendee_emails:
            body["attendees"] = [
                {
                    "emailAddress": {"address": email},
                    "type": "required"
                }
                for email in attendee_emails
            ]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://graph.microsoft.com/v1.0/me/events",
                headers={"Authorization": f"Bearer {graph_token}"},
                json=body
            )
            response.raise_for_status()
            event = response.json()

            start_str = event.get("start", {}).get("dateTime", "")
            end_str = event.get("end", {}).get("dateTime", "")

            start_utc8 = datetime.strptime(start_str[:19], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=8) if start_str else "No Start Time"
            end_utc8 = datetime.strptime(end_str[:19], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=8) if end_str else "No End Time"

            return {
                "event_id": event.get("id"),
                "subject": event.get("subject"),
                "start": start_utc8.isoformat() if isinstance(start_utc8, datetime) else start_utc8,
                "end": end_utc8.isoformat() if isinstance(end_utc8, datetime) else end_utc8,
                "webLink": event.get("webLink"),
                "status": "success"
            }
    except Exception as e:
        print(f"DEBUG: Create Calendar Event Failed: {str(e)}")
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="http", port=8004, host = "0.0.0.0")