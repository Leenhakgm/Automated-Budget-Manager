**Automated Budget Manager using WhatsApp, Flask, and Google Sheets**

This project is a smart budget management bot built using the Twilio WhatsApp API, Flask (Python), and Google Sheets. Users can interact with the bot via WhatsApp to record expenses, view data, and get dynamic access to their personal budget sheets.

## Features

- WhatsApp-based budget entry
- Google Sheets integration per user (individual spreadsheet per number)
- Dynamic link generation for users to access their sheet
- Commands like `add`, `get sheet`, and more
- Flask backend with Google Drive API and GSpread

## Tech Stack

- Python Flask (Backend)
- Twilio WhatsApp Sandbox (Bot Interface)
- Google Sheets & Google Drive API (Data Storage)
- Ngrok (for localhost exposure during development)

## Setup Instructions

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/autobudget.git
   cd autobudget
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Add your `credentials.json` from Google Cloud and place it in the root directory.

4. Run your Flask app:
   ```bash
   python app.py
   ```

5. Use ngrok to expose your Flask app (during development):
   ```bash
   ngrok http 5000
   ```

6. Update the Twilio webhook to point to your ngrok URL.

## Project Members

- Leenha K G M
- Srividhya P
- Lubhika M

---

*For educational purposes. Not for commercial use.*