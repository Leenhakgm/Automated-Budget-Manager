from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

# -------------------- Google Sheets Setup --------------------
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]
FOLDER_ID = "15b9wn341cpTbEPyr91ooXXTlgkPooX5X"  # Fixed Drive folder
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
client = gspread.authorize(creds)
user_sheet_links = {}

# -------------------- Function to Add Chart Tab --------------------
def add_chart_tab(sheet_obj):
    chart_tab = sheet_obj.add_worksheet(title="Chart", rows="20", cols="5")
    chart_tab.update("A1:B1", [["Category", "Total"]])
    chart_tab.update("A2", [["=QUERY(Sheet1!B2:C, \"select B, sum(C) where C is not null group by B label sum(C) 'Total'\")"]])

    try:
        credentials = service_account.Credentials.from_service_account_file(
            "credentials.json", scopes=SCOPE
        )
        sheets_service = build("sheets", "v4", credentials=credentials)

        chart_request = {
            "requests": [
                {
                    "addChart": {
                        "chart": {
                            "spec": {
                                "title": "Expense Summary by Category",
                                "basicChart": {
                                    "chartType": "COLUMN",
                                    "legendPosition": "BOTTOM_LEGEND",
                                    "axis": [
                                        {"position": "BOTTOM_AXIS", "title": "Category"},
                                        {"position": "LEFT_AXIS", "title": "Amount"}
                                    ],
                                    "domains": [
                                        {"domain": {"sourceRange": {"sources": [{"sheetId": chart_tab.id, "startRowIndex": 1, "endRowIndex": 20, "startColumnIndex": 0, "endColumnIndex": 1}]}}}
                                    ],
                                    "series": [
                                        {"series": {"sourceRange": {"sources": [{"sheetId": chart_tab.id, "startRowIndex": 1, "endRowIndex": 20, "startColumnIndex": 1, "endColumnIndex": 2}]}}}
                                    ],
                                }
                            },
                            "position": {
                                "newSheet": False,
                                "overlayPosition": {
                                    "anchorCell": {
                                        "sheetId": chart_tab.id,
                                        "rowIndex": 4,
                                        "columnIndex": 2
                                    },
                                    "offsetXPixels": 0,
                                    "offsetYPixels": 0
                                }
                            }
                        }
                    }
                }
            ]
        }

        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_obj.id,
            body=chart_request
        ).execute()

    except Exception as e:
        print("Error creating chart tab:", e)

# -------------------- Flask Route --------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")
    user_id = sender.replace("whatsapp:", "").replace("+", "")
    sheet_name = f"Budget_{user_id}"
    msg_lower = incoming_msg.lower()

    resp = MessagingResponse()

    # --------- Create or Load User Sheet ----------
    if user_id in user_sheet_links:
        sheet_id = user_sheet_links[user_id]
        user_sheet = client.open_by_key(sheet_id)
    else:
        try:
            user_sheet = client.open(sheet_name)
        except gspread.exceptions.SpreadsheetNotFound:
            user_sheet = client.create(sheet_name)
            user_sheet.share(None, perm_type="anyone", role="reader")
            sheet = user_sheet.sheet1
            sheet.resize(rows=100, cols=4)
            sheet.update("A1:D1", [["Timestamp", "Category", "Amount", "Note"]])
            sheet.append_row(["#BUDGET", "0", "", ""])
            add_chart_tab(user_sheet)

            try:
                credentials = service_account.Credentials.from_service_account_file(
                    "credentials.json", scopes=SCOPE
                )
                drive_service = build("drive", "v3", credentials=credentials)
                drive_service.files().update(
                    fileId=user_sheet.id,
                    addParents=FOLDER_ID,
                    removeParents="root",
                    fields="id, parents"
                ).execute()
            except Exception as e:
                print("Error moving to folder:", e)

        user_sheet_links[user_id] = user_sheet.id

    sheet = user_sheet.sheet1
    all_rows = sheet.get_all_values()
    offset = 2 if all_rows[1][0] == "#BUDGET" else 1

    # --------- Handle "get sheet" ----------
    if msg_lower == "get sheet":
        link = f"https://docs.google.com/spreadsheets/d/{user_sheet.id}/edit"
        resp.message(f"📄 Here's your personal sheet: {link}")
        return str(resp)

    # --------- Handle "reset" ----------
    if msg_lower == "reset":
        try:
            for file in client.list_spreadsheet_files():
                if file["name"] == sheet_name:
                    client.del_spreadsheet(file["id"])
                    user_sheet_links.pop(user_id, None)
                    break
        except Exception as e:
            print("Error deleting sheet:", e)

        new_sheet = client.create(sheet_name)
        new_sheet.share(None, perm_type="anyone", role="reader")
        sheet = new_sheet.sheet1
        sheet.resize(rows=100, cols=4)
        sheet.update("A1:D1", [["Timestamp", "Category", "Amount", "Note"]])
        sheet.append_row(["#BUDGET", "0", "", ""])
        add_chart_tab(new_sheet)

        try:
            credentials = service_account.Credentials.from_service_account_file(
                "credentials.json", scopes=SCOPE
            )
            drive_service = build("drive", "v3", credentials=credentials)
            drive_service.files().update(
                fileId=new_sheet.id,
                addParents=FOLDER_ID,
                removeParents="root",
                fields="id, parents"
            ).execute()
        except Exception as e:
            print("Error moving new sheet:", e)

        user_sheet_links[user_id] = new_sheet.id
        sheet_url = f"https://docs.google.com/spreadsheets/d/{new_sheet.id}/edit"
        resp.message(f"🧹 Sheet reset done!\n📄 New Sheet: {sheet_url}")
        return str(resp)

    # --------- Handle "help" ----------
    if msg_lower == "help":
        resp.message(
            "💡 *How to use this bot:*\n"
            "- Add expense: `Grocery 200`\n"
            "- Add multiple: `Milk 40\\nSnacks 50`\n"
            "- View total: `total`\n"
            "- View summary: `summary`\n"
            "- Set budget: `set budget 5000`\n"
            "- Delete entry: `delete last` or `delete 3`\n"
            "- Get your sheet: `get sheet`\n"
            "- Reset your sheet: `reset`\n"
            "- Show this message: `help`"
        )
        return str(resp)

    # --------- Handle "set budget" ----------
    if msg_lower.startswith("set budget"):
        try:
            amount = int(incoming_msg.split()[2])
            sheet.update_cell(2, 2, str(amount))
            resp.message(f"✅ Budget set to ₹{amount}")
        except:
            resp.message("⚠️ Invalid format. Use: set budget 5000")
        return str(resp)

    # --------- Handle "total" ----------
    if msg_lower == "total":
        budget = None
        records = all_rows[offset:]
        total = sum(int(row[2]) for row in records if len(row) >= 3 and row[2].isdigit())
        if all_rows[1][0] == "#BUDGET" and all_rows[1][1].isdigit():
            budget = int(all_rows[1][1])

        msg = f"💰 Total spent: ₹{total}"
        if budget:
            msg += f"\n📌 Budget: ₹{budget}"
            if total > budget:
                msg += "\n⚠️ Budget exceeded!"
        else:
            msg += "\n(No budget set. Use `set budget 5000`)"
        resp.message(msg)
        return str(resp)

    # --------- Handle "summary" ----------
    if msg_lower == "summary":
        records = all_rows[offset:]
        cat_total = defaultdict(int)
        for row in records:
            if len(row) >= 3 and row[2].isdigit():
                cat_total[row[1]] += int(row[2])
        if not cat_total:
            resp.message("📊 No expenses yet.")
        else:
            lines = [f"{cat}: ₹{amt}" for cat, amt in cat_total.items()]
            resp.message("📊 Summary:\n" + "\n".join(lines))
        return str(resp)

    # --------- Handle "delete" ----------
    if msg_lower.startswith("delete"):
        records = all_rows[offset:]
        if not records:
            resp.message("⚠️ No entries to delete.")
            return str(resp)

        parts = msg_lower.split()
        if len(parts) == 2 and parts[1] == "last":
            sheet.delete_rows(len(records) + offset)
            resp.message("🗑️ Deleted last entry.")
        elif len(parts) == 2 and parts[1].isdigit():
            idx = int(parts[1])
            if 1 <= idx <= len(records):
                sheet.delete_rows(idx + offset)
                resp.message(f"🗑️ Deleted entry #{idx}.")
            else:
                resp.message("❌ Invalid entry number.")
        else:
            resp.message("❗ Use: `delete last` or `delete 3`")
        return str(resp)

    # --------- Handle Adding Expenses ----------
    budget = int(all_rows[1][1]) if all_rows[1][0] == "#BUDGET" and all_rows[1][1].isdigit() else None
    existing_records = all_rows[offset:]
    total_before = sum(int(row[2]) for row in existing_records if len(row) >= 3 and row[2].isdigit())

    lines = incoming_msg.split('\n')
    added, skipped, total_new = [], [], 0

    for line in lines:
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].isdigit():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([timestamp, parts[0], parts[1], ""])
            added.append(f"{parts[0]} ₹{parts[1]}")
            total_new += int(parts[1])
        else:
            skipped.append(line)

    final_total = total_before + total_new
    msg = ""

    if added:
        msg += "✅ *Added:*\n" + "\n".join(added)
    if budget and final_total > budget:
        msg += f"\n\n⚠️ *Budget exceeded!*\nBudget: ₹{budget} | Spent: ₹{final_total}"
    if skipped:
        msg += "\n\n⚠️ *Skipped invalid lines:*\n" + "\n".join(skipped)
    if not msg:
        msg = "⚠️ Couldn't understand your input. Type `help` for commands."

    resp.message(msg)
    return str(resp)

# -------------------- Run Flask App --------------------
if __name__ == "__main__":
    app.run(debug=True)
