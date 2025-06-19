import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os # Import os for path handling
from typing import Optional, List


def create_rfc822_message(to_email: str, subject: str, body: str, file_paths: Optional[List[str]] = None):
    """
    Creates an RFC822 formatted message string with optional attachments that Gmail API can use.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body text
        file_paths: A list of file paths to attach (e.g., ['path/to/file1.pdf', 'path/to/image.png'])
    
    Returns:
        Base64 encoded RFC822 message string
    """
    if file_paths:
        # Create a multipart message for attachments
        msg = MIMEMultipart()
    else:
        # Create a simple text message if no attachments
        msg = MIMEText(body, 'plain')

    msg['To'] = to_email
    msg['Subject'] = subject


    # Attach the email body if it's a multipart message
    # if file_paths:
    #     msg.attach(MIMEText(body, 'plain'))

    #     for file_path in file_paths:
    #         try:
    #             # Guess the MIME type of the file
    #             import mimetypes
    #             content_type, encoding = mimetypes.guess_type(file_path)
                
    #             if content_type is None or encoding is not None:
    #                 content_type = 'application/octet-stream' # Default if type can't be guessed
                
    #             main_type, sub_type = content_type.split('/', 1)

    #             with open(file_path, 'rb') as f:
    #                 file_data = f.read()

    #             if main_type == 'text':
    #                 part = MIMEText(file_data.decode('utf-8'), _subtype=sub_type)
    #             else:
    #                 part = MIMEBase(main_type, sub_type)
    #                 part.set_payload(file_data)
    #                 encoders.encode_base64(part) # Encode content to base64

    #             # Add header with the filename
    #             filename = os.path.basename(file_path)
    #             part.add_header('Content-Disposition', 'attachment', filename=filename)
    #             msg.attach(part)

    #         except Exception as e:
    #             print(f"Error attaching file {file_path}: {e}")
    #             # You might want to handle this error more gracefully, e.g., raise an exception
    #             continue # Continue to the next file if one fails
    
    # Convert to RFC822 format and encode
    rfc822_message = msg.as_string()
    
    # Gmail API expects the message to be base64url encoded
    encoded_message = base64.urlsafe_b64encode(rfc822_message.encode('utf-8')).decode('utf-8')
    
    return encoded_message
