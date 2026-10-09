import base64
from email.message import EmailMessage

from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP

from app.auth.gmail import load_gmail_credentials


mcp = FastMCP("gmail")


def _service():
    return build(
        "gmail",
        "v1",
        credentials=load_gmail_credentials(),
        cache_discovery=False,
    )


def _raw_message(to: str, subject: str, body: str) -> str:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


@mcp.tool(
    name="list_emails",
    description="Find recent Gmail messages and return sender, subject, date, and snippet.",
)
def list_emails(query: str = "newer_than:30d", limit: int = 10) -> dict[str, object]:
    service = _service()
    response = (
        service.users()
        .messages()
        .list(userId="me", q=query.strip(), maxResults=max(1, min(limit, 20)))
        .execute()
    )
    messages = []
    for item in response.get("messages", []):
        metadata = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=item["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        headers = {
            header["name"].lower(): header["value"]
            for header in metadata.get("payload", {}).get("headers", [])
        }
        messages.append(
            {
                "id": item["id"],
                "from": headers.get("from", ""),
                "subject": headers.get("subject", ""),
                "date": headers.get("date", ""),
                "snippet": metadata.get("snippet", ""),
            }
        )
    return {"messages": messages}


@mcp.tool(
    name="draft_email",
    description="Create an unsent Gmail draft with the supplied recipient, subject, and body.",
)
def draft_email(to: str, subject: str, body: str) -> dict[str, str]:
    if not to.strip() or not subject.strip() or not body.strip():
        raise ValueError("Recipient, subject, and body are required.")
    raw = _raw_message(to.strip(), subject.strip(), body.strip())
    draft = (
        _service()
        .users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw}})
        .execute()
    )
    return {"draft_id": draft["id"], "status": "draft_created"}


@mcp.tool(
    name="send_email",
    description="Send a Gmail message to the supplied recipient with the given subject and body.",
)
def send_email(to: str, subject: str, body: str) -> dict[str, str]:
    if not to.strip() or not subject.strip() or not body.strip():
        raise ValueError("Recipient, subject, and body are required.")
    raw = _raw_message(to.strip(), subject.strip(), body.strip())
    sent = (
        _service()
        .users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )
    return {"message_id": sent["id"], "status": "sent"}


if __name__ == "__main__":
    mcp.run()
