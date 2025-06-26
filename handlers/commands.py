from telegram.ext import CommandHandler
from core.register import register
from core.trip import start_trip, end_trip
from core.report import generate_report

register_command = CommandHandler("register", register)
trip_command = CommandHandler("trip", start_trip)
return_command = CommandHandler("return", end_trip)
report_command = CommandHandler("report", generate_report)
