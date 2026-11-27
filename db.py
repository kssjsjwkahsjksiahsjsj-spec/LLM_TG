import sqlite3
import threading

connection = sqlite3.connect("bot.db",check_same_thread=False)
connection.execute("PRAGMA foreign_keys=ON")
connection.executescript(""
                         "CREATE TABLE IF NOT EXISTS users ("
                         "user_id INTEGER PRIMARY KEY,"
                         "current_dialog INTEGER"
                         ");"
                         "CREATE TABLE IF NOT EXISTS dialogs ("
                         "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                         "user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,"
                         "number INTEGER NOT NULL,"
                         "title TEXT NOT NULL"
                         ");"
                         "CREATE TABLE IF NOT EXISTS messages ("
                         "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                         "dialog_id INTEGER NOT NULL REFERENCES dialogs(id) ON DELETE CASCADE,"
                         "role TEXT NOT NULL,"
                         "content TEXT NOT NULL);")

lock = threading.Lock()

#Возвращаем номер следующего диалога
def next_number(user_id):
    return connection.execute("SELECT COALESCE(MAX(number),0) + 1 FROM dialogs WHERE user_id = ?",(user_id,)).fetchone()[0]

#Проверка существования сессии
def session_exitst(user_id):
    return connection.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone() is not None

#При начале сессии идет проверка есть ли такой пользователь, если нет, то создает его в БД
def start_session(user_id):
    with lock,connection:
        if connection.execute("SELECT 1 FROM users WHERE user_id = ?",(user_id,)).fetchone() is not None:
            return
        connection.execute("INSERT INTO users (user_id,current_dialog) VALUES (?,NULL)",(user_id,))
        current = connection.execute("INSERT INTO dialogs (user_id,number,title) VALUES (?,1,?)",(user_id,"Диалог 1"))
        connection.execute("UPDATE users SET current_dialog = ? WHERE user_id = ?", (current.lastrowid,user_id))

#Удаляем пользователя, когда он заканчивает сессию
def end_session(user_id):
    with lock,connection:
        connection.execute("DELETE FROM users WHERE user_id = ?",(user_id,))

#Получени текущего диалога
def current_dialog(user_id):
    row = connection.execute("SELECT current_dialog FROM users WHERE user_id = ?",(user_id,)).fetchone()
    return row[0] if row else ""

#При переключении чата обновляем текущий диалог
def set_current_dialog(user_id,dialog_id):
    with lock,connection:
        connection.execute("UPDATE users SET current_dialog = ? WHERE user_id = ?",(dialog_id,user_id))

#Возвращаем список диалогов
def list_dialogs(user_id):
    return connection.execute("SELECT id,title FROM dialogs WHERE user_id = ? ORDER BY id",(user_id,)).fetchall()

#При создании нового чата
def new_dialog(user_id):
    with lock,connection:
        number = next_number(user_id)
        current = connection.execute("INSERT INTO dialogs (user_id,number,title) VALUES (?,?,?)",(user_id,number,f"Диалог {number}"))
        connection.execute("UPDATE users SET current_dialog = ? WHERE user_id = ?",(current.lastrowid,user_id))
        return current.lastrowid

#Обновляем заголовок диалога
def reset_title(dialog_id):
    with lock,connection:
        connection.execute("UPDATE dialogs SET title = 'Диалог ' || number WHERE id = ?",(dialog_id))
#Удаляем диалог
def delete_dialog(user_id,dialog_id):
    with lock,connection:
        connection.execute("DELETE FROM dialogs WHERE id = ? AND user_id = ?",(dialog_id,user_id))
    if not list_dialogs(user_id):
        return new_dialog(user_id)
    if current_dialog(user_id) == dialog_id:
        set_current_dialog(user_id,list_dialogs(user_id)[0][0])
    return current_dialog(user_id)

#Добавляем отправленные в чат сообщения - в БД
def add_message(dialog_id,role,content):
    with lock,connection:
        connection.execute("INSERT INTO messages (dialog_id,role,content) VALUES (?,?,?)",(dialog_id,role,content))

#Получени последних 10 сообщений из чата
def get_history(dialog_id,limit = 10):
    rows = connection.execute("SELECT role,content FROM messages WHERE dialog_id = ? ORDER BY id DESC LIMIT ?",(dialog_id,limit)).fetchall()
    return [{"role": r,"content": c} for r,c in reversed(rows)]

#Очищаем историю сообщений
def clear_history(dialog_id):
    with lock,connection:
        connection.execute("DELETE FROM messages WHERE dialog_id = ?",(dialog_id,))

#Получение титутльника диалога
def dialog_title(dialog_id):
    row = connection.execute("SELECT title FROM dialogs WHERE id = ?",(dialog_id,)).fetchone()
    return row[0] if row else ""

#Обновляем тутиульник диалога
def set_title(dialog_id,title):
    with lock,connection:
        connection.execute("UPDATE dialogs SET title = ? WHERE id = ?",(title,dialog_id))

#Получение принадлежности диалога
def dialog_belong_to(user_id,dialog_id):
    return connection.execute("SELECT 1 FROM dialogs WHERE id = ? AND user_id = ?",(dialog_id,user_id)).fetchone() is not None