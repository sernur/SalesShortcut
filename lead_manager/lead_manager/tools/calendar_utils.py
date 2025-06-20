"""
Google Calendar utility tools for Lead Manager.
"""

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pytz

from google.adk.tools import FunctionTool
from ..config import SERVICE_ACCOUNT_FILE, SALES_EMAIL, CALENDAR_SCOPES

logger = logging.getLogger(__name__)

def generate_available_slots(start_date, end_date, busy_slots, slot_duration=60):
    """Generate available time slots between busy periods"""
    
    # Business hours: 9 AM to 6 PM
    business_start = 9
    business_end = 18
    
    available_slots = []
    current_date = start_date.date()
    end_date_only = end_date.date()
    
    while current_date <= end_date_only:
        # Skip weekends
        if current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            current_date += timedelta(days=1)
            continue
        
        # Create datetime objects for business hours
        day_start = datetime.combine(current_date, datetime.min.time().replace(hour=business_start))
        day_end = datetime.combine(current_date, datetime.min.time().replace(hour=business_end))
        
        # Add timezone info
        if hasattr(start_date, 'tzinfo') and start_date.tzinfo:
            day_start = day_start.replace(tzinfo=start_date.tzinfo)
            day_end = day_end.replace(tzinfo=start_date.tzinfo)
        
        # Find busy slots for this day
        day_busy_slots = []
        for slot in busy_slots:
            slot_start = slot['start']
            slot_end = slot['end']
            
            # Convert to same timezone if needed
            if hasattr(day_start, 'tzinfo') and day_start.tzinfo:
                if not hasattr(slot_start, 'tzinfo') or slot_start.tzinfo is None:
                    slot_start = slot_start.replace(tzinfo=day_start.tzinfo)
                if not hasattr(slot_end, 'tzinfo') or slot_end.tzinfo is None:
                    slot_end = slot_end.replace(tzinfo=day_start.tzinfo)
            
            # Check if busy slot overlaps with this day
            if (slot_start.date() == current_date or 
                slot_end.date() == current_date or 
                (slot_start.date() < current_date < slot_end.date())):
                
                # Adjust to business hours
                overlap_start = max(day_start, slot_start)
                overlap_end = min(day_end, slot_end)
                
                if overlap_start < overlap_end:
                    day_busy_slots.append({
                        'start': overlap_start,
                        'end': overlap_end,
                        'summary': slot['summary']
                    })
        
        # Sort busy slots by start time
        day_busy_slots.sort(key=lambda x: x['start'])
        
        # Find available slots
        current_time = day_start
        
        for busy_slot in day_busy_slots:
            # Check if there's time before this busy slot
            if current_time + timedelta(minutes=slot_duration) <= busy_slot['start']:
                slot_end = busy_slot['start']
                
                # Create available slots
                while current_time + timedelta(minutes=slot_duration) <= slot_end:
                    available_slots.append({
                        'start': current_time,
                        'end': current_time + timedelta(minutes=slot_duration),
                        'date': current_date.strftime('%Y-%m-%d'),
                        'time': current_time.strftime('%H:%M'),
                        'duration_minutes': slot_duration
                    })
                    current_time += timedelta(minutes=slot_duration)
            
            # Move past this busy slot
            current_time = max(current_time, busy_slot['end'])
        
        # Check for available time after last busy slot
        while current_time + timedelta(minutes=slot_duration) <= day_end:
            available_slots.append({
                'start': current_time,
                'end': current_time + timedelta(minutes=slot_duration),
                'date': current_date.strftime('%Y-%m-%d'),
                'time': current_time.strftime('%H:%M'),
                'duration_minutes': slot_duration
            })
            current_time += timedelta(minutes=slot_duration)
        
        # Move to next day
        current_date += timedelta(days=1)
    
    return available_slots

async def check_calendar_availability(days_ahead: int = 7) -> Dict[str, Any]:
    """
    Check calendar availability for the next N days.
    
    Args:
        days_ahead: Number of days to check ahead (default 7)
        
    Returns:
        Dictionary containing availability information
    """
    try:
        logger.info(f"📅 Checking calendar availability for next {days_ahead} days...")
        
        # Create credentials with delegation
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=CALENDAR_SCOPES
        )
        delegated_creds = credentials.with_subject(SALES_EMAIL)
        
        # Create Calendar service
        service = build('calendar', 'v3', credentials=delegated_creds)
        
        # Get timezone
        calendar_info = service.calendars().get(calendarId='primary').execute()
        timezone = calendar_info.get('timeZone', 'UTC')
        tz = pytz.timezone(timezone)
        
        # Check availability for specified days
        now = datetime.now(tz)
        future = now + timedelta(days=days_ahead)
        
        logger.info(f"🌍 Calendar timezone: {timezone}")
        logger.info(f"📊 Checking availability from {now.date()} to {future.date()}")
        
        # Get events for the specified period
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat(),
            timeMax=future.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        busy_slots = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            summary = event.get('summary', 'No Title')
            
            # Parse datetime
            if 'T' in start:  # Has time
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            else:  # All-day event
                start_dt = datetime.strptime(start, '%Y-%m-%d')
                end_dt = datetime.strptime(end, '%Y-%m-%d')
            
            busy_slots.append({
                'start': start_dt,
                'end': end_dt,
                'summary': summary
            })
        
        # Generate available slots
        available_slots = generate_available_slots(now, future, busy_slots)
        
        logger.info(f"✅ Found {len(available_slots)} available slots")
        
        return {
            'success': True,
            'timezone': timezone,
            'existing_events_count': len(events),
            'busy_slots': len(busy_slots),
            'available_slots': available_slots[:10],  # Return first 10 slots
            'total_available_slots': len(available_slots),
            'message': f'Calendar availability checked successfully. Found {len(available_slots)} available slots.'
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking calendar availability: {e}")
        return {
            'success': False,
            'error': str(e),
            'available_slots': [],
            'message': f'Error checking calendar availability: {str(e)}'
        }

async def create_meeting_with_lead(
    lead_name: str,
    lead_email: str,
    meeting_subject: Optional[str] = None,
    duration_minutes: int = 60,
    preferred_date: Optional[str] = None,
    preferred_time: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a meeting with a hot lead.
    
    Args:
        lead_name: Name of the lead
        lead_email: Email address of the lead
        meeting_subject: Optional custom subject line
        duration_minutes: Meeting duration in minutes (default 60)
        preferred_date: Preferred date in YYYY-MM-DD format (optional)
        preferred_time: Preferred time in HH:MM format (optional)
        
    Returns:
        Dictionary containing meeting creation result
    """
    try:
        logger.info(f"📅 Creating meeting with {lead_name} ({lead_email})...")
        
        # Create credentials with delegation
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=CALENDAR_SCOPES
        )
        delegated_creds = credentials.with_subject(SALES_EMAIL)
        
        # Create Calendar service
        service = build('calendar', 'v3', credentials=delegated_creds)
        
        # Determine meeting time
        if preferred_date and preferred_time:
            try:
                # Use preferred date/time
                meeting_datetime = datetime.strptime(f"{preferred_date} {preferred_time}", "%Y-%m-%d %H:%M")
                tz = pytz.timezone('America/New_York')  # Adjust as needed
                meeting_start = tz.localize(meeting_datetime)
            except ValueError as e:
                logger.warning(f"Invalid preferred date/time format: {e}. Using next available slot.")
                # Fall back to next available slot
                availability = await check_calendar_availability()
                if not availability['success'] or not availability['available_slots']:
                    raise Exception("No available time slots found")
                
                slot = availability['available_slots'][0]
                meeting_start = slot['start']
        else:
            # Use next available slot
            availability = await check_calendar_availability()
            if not availability['success'] or not availability['available_slots']:
                raise Exception("No available time slots found")
            
            slot = availability['available_slots'][0]
            meeting_start = slot['start']
        
        meeting_end = meeting_start + timedelta(minutes=duration_minutes)
        
        # Prepare meeting title
        if not meeting_subject:
            meeting_subject = f"Sales Discussion - {lead_name}"
        
        # Prepare meeting description
        description = f"""Meeting with {lead_name} to discuss business opportunities.

📋 Agenda:
• Introduction and overview
• Business needs assessment  
• Solution presentation
• Q&A session
• Next steps discussion

🏢 Organized by: Sales Team
📧 Contact: {SALES_EMAIL}

We look forward to speaking with you!"""
        
        # Prepare event data
        event_data = {
            'summary': meeting_subject,
            'description': description,
            'start': {
                'dateTime': meeting_start.isoformat(),
                'timeZone': str(meeting_start.tzinfo),
            },
            'end': {
                'dateTime': meeting_end.isoformat(),
                'timeZone': str(meeting_end.tzinfo),
            },
            'attendees': [
                {'email': lead_email}
            ],
            'conferenceData': {
                'createRequest': {
                    'requestId': f"{uuid.uuid4().hex}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                    {'method': 'popup', 'minutes': 30},       # 30 min before
                ],
            },
        }
        
        # Create the event
        event = service.events().insert(
            calendarId='primary',
            body=event_data,
            sendUpdates='all',
            conferenceDataVersion=1
        ).execute()
        
        # Extract Google Meet link
        meet_link = ""
        if 'conferenceData' in event and 'entryPoints' in event['conferenceData']:
            for entry_point in event['conferenceData']['entryPoints']:
                if entry_point['entryPointType'] == 'video':
                    meet_link = entry_point['uri']
                    break
        
        result = {
            'success': True,
            'meeting_id': event.get('id'),
            'title': meeting_subject,
            'start_time': meeting_start.isoformat(),
            'end_time': meeting_end.isoformat(),
            'duration': duration_minutes,
            'attendees': [lead_email],
            'meet_link': meet_link,
            'calendar_link': event.get('htmlLink'),
            'lead_name': lead_name,
            'lead_email': lead_email,
            'message': f'Meeting successfully created with {lead_name}'
        }
        
        logger.info(f"✅ Meeting created successfully!")
        logger.info(f"   Meeting ID: {event.get('id')}")
        logger.info(f"   Google Meet: {meet_link}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error creating meeting: {e}")
        return {
            'success': False,
            'error': str(e),
            'lead_name': lead_name,
            'lead_email': lead_email,
            'message': f'Error creating meeting with {lead_name}: {str(e)}'
        }

# Create the tools
check_availability_tool = FunctionTool(func=check_calendar_availability)

create_meeting_tool = FunctionTool(func=create_meeting_with_lead)