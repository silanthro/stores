# Tools

## `comms.gmail.send_email_via_gmail`

This requires the following environment variables:

- `GMAIL_ADDRESS`: The Gmail address used to send the email
- `GMAIL_PASSWORD`: This is a 16-character password created via https://myaccount.google.com/apppasswords

In order to create the 16-character password, 2-Step Verification must be set up.

For more details, see the Gmail Help article at https://support.google.com/mail/answer/185833?hl=en

## `comms.telegram.send_telegram_message`

This requires the following environment variable:

- `TELEGRAM_API_TOKEN`: The API token associated with the Telegram bot used to send the message

First create a Telegram bot by sending "/newbot" to the @BotFather Telegram account. Then follow the chat instructions to create a bot and receive the API token.

Note, to send a message to a specific recipient, the recipient needs to first initiate a conversation with the bot.
