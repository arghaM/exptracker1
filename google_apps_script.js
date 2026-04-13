/**
 * Google Apps Script — Telegram Poller → Google Sheet Logger
 *
 * This uses a time-based trigger to poll Telegram every minute
 * and log messages to the sheet. No webhook needed.
 *
 * Setup:
 * 1. Open https://script.google.com and create a new project
 * 2. Paste this entire file into Code.gs
 * 3. Update BOT_TOKEN and CHAT_ID below
 * 4. Run "setup()" once from the editor (Run button ▶)
 *    - This creates a trigger that runs every minute
 *    - Authorize when prompted
 * 5. Done! Messages will auto-log to the sheet.
 *
 * To stop: Run "removeTrigger()" from the editor
 */

var BOT_TOKEN = "YOUR_BOT_TOKEN_HERE";
var CHAT_ID = "YOUR_CHAT_ID_HERE";
var SHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE";
var SHEET_NAME = "Sheet1";

function setup() {
  // Remove any existing triggers first
  removeTrigger();

  // Create a trigger that runs every 1 minute
  ScriptApp.newTrigger("pollTelegram")
    .timeBased()
    .everyHours(1)
    .create();

  Logger.log("Trigger created! Messages will be polled every minute.");
}

function removeTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    ScriptApp.deleteTrigger(triggers[i]);
  }
  Logger.log("All triggers removed.");
}

function pollTelegram() {
  var props = PropertiesService.getScriptProperties();
  var lastUpdateId = parseInt(props.getProperty("last_update_id") || "0");

  var url = "https://api.telegram.org/bot" + BOT_TOKEN + "/getUpdates?timeout=0&allowed_updates=%5B%22message%22%5D";
  if (lastUpdateId > 0) {
    url += "&offset=" + (lastUpdateId + 1);
  }

  var response;
  try {
    response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  } catch (err) {
    Logger.log("Fetch error: " + err);
    return;
  }

  var data = JSON.parse(response.getContentText());
  if (!data.ok || !data.result || data.result.length === 0) {
    return;
  }

  var sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
  var newLastUpdateId = lastUpdateId;

  for (var i = 0; i < data.result.length; i++) {
    var update = data.result[i];
    if (update.update_id > newLastUpdateId) {
      newLastUpdateId = update.update_id;
    }

    var message = update.message;
    if (!message || !message.text) continue;
    if (String(message.chat.id) !== CHAT_ID) continue;

    var timestamp = new Date(message.date * 1000).toISOString();
    var chatId = String(message.chat.id);
    var messageId = message.message_id;
    var text = message.text;

    sheet.appendRow([timestamp, chatId, messageId, text]);
  }

  props.setProperty("last_update_id", String(newLastUpdateId));
}
