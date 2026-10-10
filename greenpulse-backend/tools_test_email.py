import json

from greenpulse.email_service import (
    EmailService,
    EmailServiceError,
)


def main():
    print("======================================")
    print("GREENPULSE GMAIL TEST")
    print("======================================")
    print()

    service = EmailService()

    print("Connecting to Gmail...")

    try:
        messages = service.get_relevant_recent_emails(
            max_messages=5
        )

    except EmailServiceError as error:
        print()
        print("GMAIL TEST FAILED")
        print(error)
        return

    print("Gmail connection successful.")
    print()

    print(
        f"Relevant messages found: {len(messages)}"
    )

    if messages:
        print()
        print(json.dumps(
            messages,
            indent=2,
            ensure_ascii=False
        ))
    else:
        print(
            "No relevant gardening/weather emails "
            "were found in the recent Inbox messages."
        )

    print()
    print("GMAIL TEST PASSED")


if __name__ == "__main__":
    main()