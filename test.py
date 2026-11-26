import db
db.start_session(123)
print(db.list_dialogs(123))