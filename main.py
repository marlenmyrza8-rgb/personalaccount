import asyncio
import json
import os
import re
from datetime import datetime, timedelta, date

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from schedule_generator import generate_schedule_image
import random
from database import (
    init_db, is_admin, ADMIN_ID,
    add_user, add_user_curator, get_user_curators,
    get_all_users, get_curator_students,
    get_user_count, get_user_progress,
    get_top_users, reset_weekly_scores,
    add_curator, remove_curator, get_curators,
    get_curator_code,
    add_task, get_active_tasks, delete_task,
    mark_task_notified, was_notified,
    set_guide, get_guide,
    add_book_to_db, get_books, get_book_file, delete_book_from_db,
    add_score, set_schedule, get_schedule,
    add_question, get_all_questions, get_question_by_id,
    get_question_count, delete_question,
    start_quiz_session, get_quiz_session, update_quiz_session, clear_quiz_session,
)

# ---------------------------------------------------------------------------
# Баптаулар
# ---------------------------------------------------------------------------
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise RuntimeError("Environment variable BOT_TOKEN is required.")

bot = Bot(token=API_TOKEN)
dp  = Dispatcher()

SUBJECTS = [
    "Ағылшын тілі", "Биология", "География", "Геометрия",
    "Дүниежүзі тарихы", "Информатика", "Қазақ әдебиеті", "Қазақ тілі",
    "Қазақстан тарихы", "Құқық негіздері", "Математика", "Математикалық сауаттылық",
    "Оқу сауаттылығы", "Орыс әдебиеті", "Орыс тілі", "Физика", "Химия",
    "Шығармашылық емтихан",
]

# ---------------------------------------------------------------------------
# Рөл анықтағыштар
# ---------------------------------------------------------------------------
def is_main_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def is_curator_only(user_id: int) -> bool:
    return is_admin(user_id) and user_id != ADMIN_ID

# ---------------------------------------------------------------------------
# Пернетақталар
# ---------------------------------------------------------------------------
student_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Дедлайндар"),  KeyboardButton(text="📊 Үлгерім")],
        [KeyboardButton(text="📚 Пәндер"),       KeyboardButton(text="🧠 Daily Challenge")],
        [KeyboardButton(text="📖 Гайд"),         KeyboardButton(text="🗓 Расписание")],
    ],
    resize_keyboard=True,
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Дедлайндар"),  KeyboardButton(text="📊 Үлгерім")],
        [KeyboardButton(text="📚 Пәндер"),       KeyboardButton(text="🧠 Daily Challenge")],
        [KeyboardButton(text="📖 Гайд"),         KeyboardButton(text="🗓 Расписание")],
        [KeyboardButton(text="⚙️ Админ панель")],
    ],
    resize_keyboard=True,
)

curator_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Дедлайндар"),  KeyboardButton(text="📊 Үлгерім")],
        [KeyboardButton(text="📚 Пәндер"),       KeyboardButton(text="🧠 Daily Challenge")],
        [KeyboardButton(text="📖 Гайд"),         KeyboardButton(text="🗓 Расписание")],
        [KeyboardButton(text="🧑‍💼 Куратор панель")],
    ],
    resize_keyboard=True,
)

def get_kb_for(user_id: int):
    if is_main_admin(user_id):
        return admin_kb
    if is_curator_only(user_id):
        return curator_kb
    return student_kb

def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Гайд қосу/өзгерту",    callback_data="adm_setguide")],
        [InlineKeyboardButton(text="📚 Кітап қосу",            callback_data="adm_addbook")],
        [InlineKeyboardButton(text="🗑 Кітап жою",             callback_data="adm_delbook")],
        [InlineKeyboardButton(text="➕ Тапсырма қосу",         callback_data="adm_addtask")],
        [InlineKeyboardButton(text="❌ Тапсырма жою",          callback_data="adm_deltask")],
        [InlineKeyboardButton(text="📢 Хабар тарату (барлық)", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика",            callback_data="adm_stats")],
        [InlineKeyboardButton(text="👤 Куратор қосу",          callback_data="adm_addcurator")],
        [InlineKeyboardButton(text="🚫 Куратор жою",           callback_data="adm_removecurator")],
        [InlineKeyboardButton(text="🔄 Апталық баллды нөлдеу", callback_data="adm_resetweekly")],
        [InlineKeyboardButton(text="❓ Сұрақ қосу",              callback_data="adm_addquestion")],
        [InlineKeyboardButton(text="🗑 Сұрақ жою",               callback_data="adm_delquestion")],
        [InlineKeyboardButton(text="📋 Сұрақтар саны",           callback_data="adm_questioncount")],
    ])

def curator_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Тапсырма қосу",    callback_data="cur_addtask")],
        [InlineKeyboardButton(text="📢 Оқушыларға хабар", callback_data="cur_broadcast")],
        [InlineKeyboardButton(text="🏅 Балл қосу",        callback_data="cur_addscore")],
        [InlineKeyboardButton(text="👥 Оқушылар саны",    callback_data="cur_stats")],
    ])

def subjects_kb(prefix: str) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(SUBJECTS) - 1, 2):
        rows.append([
            InlineKeyboardButton(text=SUBJECTS[i],     callback_data=f"{prefix}_{i}"),
            InlineKeyboardButton(text=SUBJECTS[i + 1], callback_data=f"{prefix}_{i+1}"),
        ])
    if len(SUBJECTS) % 2:
        rows.append([InlineKeyboardButton(text=SUBJECTS[-1], callback_data=f"{prefix}_{len(SUBJECTS)-1}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ---------------------------------------------------------------------------
# FSM күйлері
# ---------------------------------------------------------------------------
class TaskState(StatesGroup):
    waiting_for_title    = State()
    waiting_for_deadline = State()

class CurTaskState(StatesGroup):
    waiting_for_title    = State()
    waiting_for_deadline = State()

class GuideState(StatesGroup):
    waiting_for_content = State()

class BookState(StatesGroup):
    waiting_for_title = State()
    waiting_for_file  = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

class CurBroadcastState(StatesGroup):
    waiting_for_message = State()

class CuratorState(StatesGroup):
    waiting_for_add_id = State()

class RegisterState(StatesGroup):
    waiting_for_curator_id = State()

class ScheduleState(StatesGroup):
    waiting_for_text = State()

class AIScheduleState(StatesGroup):
    waiting_for_input = State()

class ScoreState(StatesGroup):
    waiting_for_student = State()
    waiting_for_score   = State()

class AddQuestionState(StatesGroup):
    waiting_for_subject  = State()
    waiting_for_question = State()
    waiting_for_options  = State()
    waiting_for_correct  = State()

# ---------------------------------------------------------------------------
# Хелперлер
# ---------------------------------------------------------------------------
async def broadcast_all(text: str) -> int:
    sent = 0
    for user_id in get_all_users():
        try:
            await bot.send_message(user_id, text, parse_mode="Markdown")
            sent += 1
        except Exception:
            pass
    return sent

async def broadcast_to(user_ids: list[int], text: str) -> int:
    sent = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text, parse_mode="Markdown")
            sent += 1
        except Exception:
            pass
    return sent

def parse_schedule_text(user_text: str) -> dict:
    """
    AI-сыз парсер. Формат:
    Математика 10:00 дс сс бс
    Физика 14:00 жм
    Химия 11:00 ср бс жс
    """
    DAY_MAP = {
        # қазақша қысқа
        "дс": 0, "сс": 1, "ср": 2, "бс": 3, "жм": 4, "сб": 5, "жс": 6,
        # қазақша толық
        "дүйсенбі": 0, "сейсенбі": 1, "сәрсенбі": 2, "бейсенбі": 3,
        "жұма": 4, "сенбі": 5, "жексенбі": 6,
        # орысша
        "пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6,
        "понедельник": 0, "вторник": 1, "среда": 2, "четверг": 3,
        "пятница": 4, "суббота": 5, "воскресенье": 6,
        # ағылшынша
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    }
    TIME_RE = re.compile(r"\b(\d{1,2}:\d{2})\b")
    subjects = []

    for line in user_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        # Уақытты табу
        time_match = TIME_RE.search(line)
        time = time_match.group(1) if time_match else "09:00"
        line_no_time = TIME_RE.sub("", line).strip()

        # Күндерді табу
        tokens = re.split(r"[,\s]+", line_no_time.lower())
        days = []
        name_tokens = []
        for token in tokens:
            token = token.strip(".,;:-")
            if token in DAY_MAP:
                d = DAY_MAP[token]
                if d not in days:
                    days.append(d)
            elif token:
                name_tokens.append(token)

        # Пән атын қалпына келтіру
        # Бастапқы регистрді сақтау үшін original line-дан аламыз
        original_tokens = re.split(r"[,\s]+", line_no_time)
        orig_name_parts = []
        for t in original_tokens:
            t_clean = t.strip(".,;:-")
            if t_clean.lower() not in DAY_MAP and t_clean:
                orig_name_parts.append(t_clean)
        name = " ".join(orig_name_parts).strip()

        if not name:
            continue
        if not days:
            days = [0, 1, 2, 3, 4]  # жұмыс күндері

        subjects.append({"name": name, "time": time, "days": sorted(days)})

    return {"subjects": subjects}


async def call_claude_schedule(user_text: str) -> dict:
    """AI-сыз локальды парсер."""
    return parse_schedule_text(user_text)

# ===========================================================================
# СТУДЕНТ БӨЛІМІ
# ===========================================================================

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    add_user(user_id)

    if is_admin(user_id):
        await message.answer(
            f"👋 Сәлем, *{message.from_user.first_name}*!\n"
            f"ҰБТ дайындық курсының ресми ботына қош келдіңіз!\n\n"
            f"_(Сіздің ID: `{user_id}`)_",
            reply_markup=get_kb_for(user_id),
            parse_mode="Markdown",
        )
        return

    existing = get_user_curators(user_id)
    if existing:
        await message.answer(
            f"👋 Сәлем, *{message.from_user.first_name}*!\n"
            f"ҰБТ дайындық курсының ресми ботына қош келдіңіз!\n\n"
            f"_(Сіздің ID: `{user_id}`)_",
            reply_markup=get_kb_for(user_id),
            parse_mode="Markdown",
        )
        return

    skip_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭ Өткізіп жіберу")]],
        resize_keyboard=True,
    )
    await message.answer(
        f"👋 Сәлем, *{message.from_user.first_name}*!\n"
        f"ҰБТ дайындық курсының ресми ботына қош келдіңіз!\n\n"
        f"📌 Куратордың Telegram *ID-ін* жазыңыз.\n"
        f"_(Білмесеңіз — '⏭ Өткізіп жіберу' басыңыз)_",
        reply_markup=skip_kb,
        parse_mode="Markdown",
    )
    await state.set_state(RegisterState.waiting_for_curator_id)


@dp.message(RegisterState.waiting_for_curator_id)
async def register_curator_id(message: types.Message, state: FSMContext) -> None:
    user_id = message.from_user.id

    if message.text == "⏭ Өткізіп жіберу":
        await state.clear()
        await message.answer(
            "✅ Тіркелу аяқталды! Кейін куратор қосқыңыз келсе — /addcurator жазыңыз.",
            reply_markup=get_kb_for(user_id),
        )
        return

    try:
        curator_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID тек сан болуы керек. Қайта жазыңыз немесе ⏭ басыңыз.")
        return

    if not is_admin(curator_id):
        await message.answer("⚠️ Бұл ID бойынша куратор табылмады. Қайта жазыңыз немесе ⏭ басыңыз.")
        return

    add_user_curator(user_id, curator_id)
    await state.clear()
    await message.answer(
        "✅ Куратормен сәтті байластырылдыңыз!",
        reply_markup=get_kb_for(user_id),
    )


@dp.message(Command("addcurator"))
async def cmd_add_my_curator(message: types.Message, state: FSMContext) -> None:
    if is_admin(message.from_user.id):
        return
    skip_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭ Өткізіп жіберу")]],
        resize_keyboard=True,
    )
    await message.answer(
        "📌 Куратордың Telegram *ID-ін* жазыңыз:",
        reply_markup=skip_kb,
        parse_mode="Markdown",
    )
    await state.set_state(RegisterState.waiting_for_curator_id)


@dp.message(F.text == "📚 Пәндер")
async def guide_menu(message: types.Message) -> None:
    await message.answer(
        "📚 *Пәндер және Кітаптар:*\nПәніңізді таңдаңыз:",
        reply_markup=subjects_kb("subj"),
        parse_mode="Markdown",
    )

@dp.callback_query(F.data.startswith("subj_"))
async def subject_chosen(callback: types.CallbackQuery) -> None:
    idx        = int(callback.data.split("_")[1])
    subject    = SUBJECTS[idx]
    guide_data = get_guide(subject)
    text    = guide_data[0] if guide_data else f"⏳ *{subject}* пәні бойынша гайд әлі жүктелмеген."
    file_id = guide_data[1] if guide_data else None
    books_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Кітаптарды көру", callback_data=f"showbooks_{idx}")]
    ])
    try:
        await callback.message.delete()
    except Exception:
        pass
    if file_id:
        await callback.message.answer_document(file_id, caption=text, reply_markup=books_btn, parse_mode="Markdown")
    else:
        await callback.message.answer(text, reply_markup=books_btn, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("showbooks_"))
async def show_books(callback: types.CallbackQuery) -> None:
    idx     = int(callback.data.split("_")[1])
    subject = SUBJECTS[idx]
    books   = get_books(subject)
    if not books:
        await callback.answer("Бұл пән бойынша кітаптар жоқ.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=row["title"], callback_data=f"getbook_{row['id']}")]
        for row in books
    ])
    await callback.message.answer(f"📚 *{subject}* бойынша кітаптар:", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("getbook_"))
async def send_book(callback: types.CallbackQuery) -> None:
    book_id = int(callback.data.split("_")[1])
    file_id = get_book_file(book_id)
    if file_id:
        await callback.message.answer_document(file_id)
        await callback.answer()
    else:
        await callback.answer("❌ Файл табылмады.", show_alert=True)

@dp.message(F.text == "📖 Гайд")
async def guide_static(message: types.Message) -> None:
    await message.answer(
        "📖 *Гайд*\n\n"
        "Мұнда курс бойынша негізгі ақпарат болады.\n"
        "_(Жақын арада толтырылады)_",
        parse_mode="Markdown",
    )

@dp.message(F.text == "📊 Үлгерім")
async def show_progress(message: types.Message) -> None:
    done, total, weekly = get_user_progress(message.from_user.id)
    await message.answer(
        f"📈 *Сіздің үлгеріміңіз:*\n\n"
        f"✅ Орындалған тапсырмалар: *{done}*\n"
        f"🏆 Жалпы балл: *{total}*\n"
        f"🔥 Осы аптада: *{weekly}*",
        parse_mode="Markdown",
    )

@dp.message(F.text == "📅 Дедлайндар")
async def show_deadlines(message: types.Message) -> None:
    uid = message.from_user.id
    tasks = get_active_tasks(curator_id=uid) if is_curator_only(uid) else get_active_tasks()
    if not tasks:
        await message.answer("🎉 Қазіргі уақытта белсенді тапсырмалар жоқ!")
        return
    lines = ["⏳ *Алдағы дедлайндар:*\n"]
    for task in tasks:
        deadline_dt = datetime.strptime(task["deadline"], "%Y-%m-%d %H:%M")
        time_left   = deadline_dt - datetime.now()
        if time_left.total_seconds() > 0:
            days  = time_left.days
            hours = time_left.seconds // 3600
            lines.append(f"📌 *{task['title']}*\n🕒 {task['deadline']} (Қалды: {days} күн {hours} сағат)\n")
        else:
            lines.append(f"❌ *{task['title']}*\n🕒 Дедлайн өтіп кетті: {task['deadline']}\n")
    await message.answer("\n".join(lines), parse_mode="Markdown")

@dp.message(F.text == "🧠 Daily Challenge")
async def daily_challenge(message: types.Message) -> None:
    user_id = message.from_user.id
    today   = date.today().isoformat()

    session = get_quiz_session(user_id)
    if session and session["date"] == today:
        idx   = session["current_idx"]
        total = len(session["question_ids"])
        if idx >= total:
            await message.answer(
                f"✅ Бүгінгі тест аяқталды!\n\n"
                f"🏆 Нәтиже: *{session['correct_count']}/{total}* дұрыс\n\n"
                f"Ертең жаңа 10 сұрақ келеді!",
                parse_mode="Markdown",
            )
            return
        await send_quiz_question(message.from_user, session, idx)
        return

    all_q = get_all_questions()
    if not all_q:
        await message.answer("⚠️ Сұрақтар базасы бос. Админ сұрақ қосуы керек.")
        return

    count  = min(10, len(all_q))
    picked = random.sample([q["id"] for q in all_q], count)
    start_quiz_session(user_id, picked, today)
    session = get_quiz_session(user_id)

    await message.answer(
        f"🧠 *Daily Challenge басталды!*\n\n"
        f"📝 {count} сұрақ дайын. Бастайық!\n"
        f"_Әр сұраққа A, B, C немесе D батырмасын басыңыз._",
        parse_mode="Markdown",
    )
    await send_quiz_question(message.from_user, session, 0)


async def send_quiz_question(user, session: dict, idx: int) -> None:
    qid   = session["question_ids"][idx]
    q     = get_question_by_id(qid)
    total = len(session["question_ids"])
    if q is None:
        return
    text = (
        f"🧠 *Сұрақ {idx + 1}/{total}*\n"
        f"📚 _{q['subject']}_\n\n"
        f"*{q['question']}*\n\n"
        f"🅰️ {q['option_a']}\n"
        f"🅱️ {q['option_b']}\n"
        f"🅲 {q['option_c']}\n"
        f"🅳 {q['option_d']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="A", callback_data=f"quiz_{qid}_{idx}_0"),
        InlineKeyboardButton(text="B", callback_data=f"quiz_{qid}_{idx}_1"),
        InlineKeyboardButton(text="C", callback_data=f"quiz_{qid}_{idx}_2"),
        InlineKeyboardButton(text="D", callback_data=f"quiz_{qid}_{idx}_3"),
    ]])
    await bot.send_message(user.id, text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("quiz_"))
async def quiz_answer(callback: types.CallbackQuery) -> None:
    parts   = callback.data.split("_")
    qid     = int(parts[1])
    idx     = int(parts[2])
    answer  = int(parts[3])
    user_id = callback.from_user.id

    session = get_quiz_session(user_id)
    if not session:
        await callback.answer("Сессия табылмады.", show_alert=True)
        return

    q       = get_question_by_id(qid)
    correct = q["correct"]
    options = [q["option_a"], q["option_b"], q["option_c"], q["option_d"]]
    labels  = ["A", "B", "C", "D"]

    is_correct  = (answer == correct)
    new_correct = session["correct_count"] + (1 if is_correct else 0)
    new_idx     = idx + 1
    total       = len(session["question_ids"])
    update_quiz_session(user_id, new_idx, new_correct)

    if is_correct:
        result_text = f"✅ *Дұрыс!* {labels[correct]}) {options[correct]}"
    else:
        result_text = (
            f"❌ *Қате!* Сіз: {labels[answer]}) {options[answer]}\n"
            f"✅ Дұрыс жауап: {labels[correct]}) {options[correct]}"
        )

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(result_text, parse_mode="Markdown")
    await callback.answer()

    if new_idx < total:
        session["current_idx"]   = new_idx
        session["correct_count"] = new_correct
        await send_quiz_question(callback.from_user, session, new_idx)
    else:
        pct   = int(new_correct / total * 100)
        emoji = "🏆" if pct >= 80 else "👍" if pct >= 60 else "📚"
        msg   = "Керемет! 🔥" if pct >= 80 else "Жақсы! Кітап оқыңыз! 📖" if pct >= 60 else "Тырысып көріңіз! 💪"
        await callback.message.answer(
            f"{emoji} *Тест аяқталды!*\n\n"
            f"✅ Дұрыс: *{new_correct}/{total}*\n"
            f"📊 Нәтиже: *{pct}%*\n\n{msg}",
            parse_mode="Markdown",
        )
        clear_quiz_session(user_id)


async def send_daily_challenge_to_all() -> None:
    all_q = get_all_questions()
    if not all_q:
        return
    today   = date.today().isoformat()
    count   = min(10, len(all_q))
    all_ids = [q["id"] for q in all_q]
    for user_id in get_all_users():
        try:
            picked = random.sample(all_ids, count)
            start_quiz_session(user_id, picked, today)
            await bot.send_message(
                user_id,
                f"🧠 *Бүгінгі Daily Challenge дайын!*\n\n"
                f"📝 {count} сұрақ күтіп тұр.\n"
                f"Төмендегі батырманы басыңыз!",
                parse_mode="Markdown",
            )
        except Exception:
            pass


# ===========================================================================
# РАСПИСАНИЕ
# ===========================================================================

@dp.message(F.text == "🗓 Расписание")
async def show_schedule(message: types.Message) -> None:
    user_id  = message.from_user.id
    schedule = get_schedule(user_id)

    edit_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Өзгерту",        callback_data="edit_schedule")],
        [InlineKeyboardButton(text="🗓 Кесте жасау (авто)", callback_data="ai_schedule")],
    ])
    add_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Өзім жазамын",   callback_data="edit_schedule")],
        [InlineKeyboardButton(text="🗓 Кесте жасау (авто)", callback_data="ai_schedule")],
    ])

    if not schedule:
        await message.answer("🗓 Расписание әлі жоқ.", reply_markup=add_kb)
        return

    text      = schedule["text"] or ""
    file_id   = schedule["file_id"] or ""
    file_type = schedule["file_type"] or ""
    caption   = f"🗓 *Сіздің расписаниеңіз:*\n\n{text}" if text else "🗓 *Сіздің расписаниеңіз:*"

    if file_type == "photo" and file_id:
        await message.answer_photo(file_id, caption=caption, reply_markup=edit_kb, parse_mode="Markdown")
    elif file_type == "document" and file_id:
        await message.answer_document(file_id, caption=caption, reply_markup=edit_kb, parse_mode="Markdown")
    else:
        await message.answer(caption, reply_markup=edit_kb, parse_mode="Markdown")


@dp.callback_query(F.data == "edit_schedule")
async def edit_schedule_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(
        "✏️ Жаңа расписаниені жіберіңіз:\n\n"
        "• *Мәтін* — тікелей жазыңыз\n"
        "• *Сурет* — фото жіберіңіз\n"
        "• *Файл* — PDF/DOC жіберіңіз",
        parse_mode="Markdown",
    )
    await state.set_state(ScheduleState.waiting_for_text)
    await callback.answer()


@dp.message(ScheduleState.waiting_for_text)
async def save_schedule(message: types.Message, state: FSMContext) -> None:
    user_id   = message.from_user.id
    text      = message.text or message.caption or ""
    file_id   = ""
    file_type = ""

    if message.photo:
        file_id   = message.photo[-1].file_id
        file_type = "photo"
    elif message.document:
        file_id   = message.document.file_id
        file_type = "document"
    elif not text:
        await message.answer("⚠️ Мәтін, сурет немесе файл жіберіңіз.")
        return

    set_schedule(user_id, text, file_id, file_type)
    await message.answer("✅ Расписание сақталды!")
    await state.clear()


@dp.callback_query(F.data == "ai_schedule")
async def ai_schedule_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(
        "🤖 *AI Кесте жасаушы*\n\n"
        "Пәндеріңіз бен уақыттарыңызды еркін жазыңыз.\n\n"
        "*Мысалдар:*\n"
        "• Математика дүйсенбі сейсенбі 10:00\n"
        "• Физика жұма 14:00, Химия сәрсенбі бейсенбі 11:00\n"
        "• Ағылшын күн сайын 09:00\n\n"
        "_Бот апталық кесте суретін жасайды!_",
        parse_mode="Markdown",
    )
    await state.set_state(AIScheduleState.waiting_for_input)
    await callback.answer()


@dp.message(AIScheduleState.waiting_for_input)
async def ai_schedule_generate(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    thinking_msg = await message.answer("⏳ AI кесте жасап жатыр, күте тұрыңыз...")

    try:
        schedule_data = await call_claude_schedule(message.text)
        if not schedule_data.get("subjects"):
            await thinking_msg.edit_text("❌ Пәндерді анықтай алмадым. Қайта жазып көріңіз.")
            return

        name    = message.from_user.first_name or ""
        img_buf = generate_schedule_image(schedule_data, student_name=name)
        photo   = BufferedInputFile(img_buf.read(), filename="schedule.png")

        save_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💾 Расписание ретінде сақтау", callback_data="save_ai_schedule")],
            [InlineKeyboardButton(text="🔄 Қайта жасау", callback_data="ai_schedule")],
        ])

        await thinking_msg.delete()
        sent = await message.answer_photo(
            photo,
            caption=f"✅ *AI жасаған апталық кесте*\n_{len(schedule_data['subjects'])} пән табылды_",
            reply_markup=save_kb,
            parse_mode="Markdown",
        )

        await state.update_data(
            photo_file_id=sent.photo[-1].file_id,
        )

    except Exception as e:
        await thinking_msg.edit_text(f"❌ Қате орын алды: {str(e)[:150]}\n\nҚайта жазып көріңіз.")


@dp.callback_query(F.data == "save_ai_schedule")
async def save_ai_schedule(callback: types.CallbackQuery, state: FSMContext) -> None:
    data    = await state.get_data()
    file_id = data.get("photo_file_id", "")
    if file_id:
        set_schedule(callback.from_user.id, text="AI кесте", file_id=file_id, file_type="photo")
        await callback.message.answer("✅ Кесте расписание ретінде сақталды!")
    else:
        await callback.answer("Қате: сурет табылмады.", show_alert=True)
    await state.clear()
    await callback.answer()

# ===========================================================================
# БАС АДМИН ПАНЕЛЬ
# ===========================================================================

@dp.message(F.text == "⚙️ Админ панель")
async def admin_panel(message: types.Message) -> None:
    if not is_main_admin(message.from_user.id): return
    await message.answer("⚙️ *Админ панель*", reply_markup=admin_panel_kb(), parse_mode="Markdown")

@dp.callback_query(F.data == "adm_setguide")
async def adm_setguide(callback: types.CallbackQuery) -> None:
    await callback.message.answer("📝 Қай пәнге гайд қосасыз?", reply_markup=subjects_kb("setguide"))
    await callback.answer()

@dp.callback_query(F.data == "adm_addbook")
async def adm_addbook(callback: types.CallbackQuery) -> None:
    await callback.message.answer("📚 Қай пәнге кітап қосасыз?", reply_markup=subjects_kb("addbook"))
    await callback.answer()

@dp.callback_query(F.data == "adm_delbook")
async def adm_delbook(callback: types.CallbackQuery) -> None:
    await callback.message.answer("🗑 Қай пәннің кітабын жоясыз?", reply_markup=subjects_kb("delbook"))
    await callback.answer()

@dp.callback_query(F.data == "adm_addtask")
async def adm_addtask(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("📝 Жаңа тапсырманың атын жазыңыз:")
    await state.set_state(TaskState.waiting_for_title)
    await callback.answer()

@dp.callback_query(F.data == "adm_deltask")
async def adm_deltask(callback: types.CallbackQuery) -> None:
    tasks = get_active_tasks()
    if not tasks:
        await callback.answer("Тапсырмалар жоқ.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"❌ {t['title']}", callback_data=f"deltask_{t['id']}")]
        for t in tasks
    ])
    await callback.message.answer("Жойылатын тапсырманы таңдаңыз:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("📢 Барлық студенттерге жіберілетін хабарды жазыңыз:")
    await state.set_state(BroadcastState.waiting_for_message)
    await callback.answer()

@dp.callback_query(F.data == "adm_stats")
async def adm_stats(callback: types.CallbackQuery) -> None:
    total_users = get_user_count()
    top         = get_top_users(5)
    tasks_count = len(get_active_tasks())
    curators    = get_curators()
    top_lines   = "\n".join(
        f"{i+1}. `{row['id']}` — {row['total_score']} балл" for i, row in enumerate(top)
    ) or "Мәлімет жоқ"
    lines = [f"• `{c['id']}` — {len(get_curator_students(c['id']))} оқушы" for c in curators]
    text = (
            f"📊 *Статистика*\n\n"
            f"👤 Студенттер саны: *{total_users}*\n"
            f"📌 Белсенді тапсырмалар: *{tasks_count}*\n\n"
            f"🧑‍💼 *Кураторлар ({len(curators)}):*\n" + ("\n".join(lines) or "Жоқ") +
            f"\n\n🏆 *Топ-5 студент:*\n{top_lines}"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "adm_addcurator")
async def adm_addcurator(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("👤 Жаңа куратордың Telegram *ID-ін* жазыңыз:", parse_mode="Markdown")
    await state.set_state(CuratorState.waiting_for_add_id)
    await callback.answer()

@dp.callback_query(F.data == "adm_removecurator")
async def adm_removecurator(callback: types.CallbackQuery) -> None:
    curators = get_curators()
    if not curators:
        await callback.answer("Кураторлар жоқ.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑 {row['id']} (код: {row['code']})", callback_data=f"delcurator_{row['id']}")]
        for row in curators
    ])
    await callback.message.answer("🚫 Жойылатын куратор:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "adm_resetweekly")
async def adm_resetweekly(callback: types.CallbackQuery) -> None:
    if not is_main_admin(callback.from_user.id):
        await callback.answer("Тек бас админ орындай алады.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Иә, нөлдеу",    callback_data="resetweekly_confirm")],
        [InlineKeyboardButton(text="❌ Жоқ, болдырма", callback_data="resetweekly_cancel")],
    ])
    await callback.message.answer("⚠️ Барлық апталық баллдар нөлденеді. Сенімдісіз бе?", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "resetweekly_confirm")
async def resetweekly_confirm(callback: types.CallbackQuery) -> None:
    reset_weekly_scores()
    await callback.message.answer("✅ Барлық апталық баллдар нөлденді.")
    await callback.answer()

@dp.callback_query(F.data == "resetweekly_cancel")
async def resetweekly_cancel(callback: types.CallbackQuery) -> None:
    await callback.message.answer("Болдырылмады.")
    await callback.answer()

# ===========================================================================
# QUIZ СҰРАҚТАРЫН БАСҚАРУ (бас админ)
# ===========================================================================

@dp.callback_query(F.data == "adm_questioncount")
async def adm_questioncount(callback: types.CallbackQuery) -> None:
    count = get_question_count()
    await callback.message.answer(f"📋 Сұрақтар базасында: *{count}* сұрақ бар.", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "adm_addquestion")
async def adm_addquestion(callback: types.CallbackQuery, state: FSMContext) -> None:
    if not is_main_admin(callback.from_user.id):
        await callback.answer("Тек бас админ.", show_alert=True)
        return
    await callback.message.answer(
        "❓ *Жаңа сұрақ қосу*\n\n"
        "1-қадам: Пән атын жазыңыз\n"
        "_(мысалы: Математика, Физика, Қазақстан тарихы)_",
        parse_mode="Markdown",
    )
    await state.set_state(AddQuestionState.waiting_for_subject)
    await callback.answer()

@dp.message(AddQuestionState.waiting_for_subject)
async def aq_subject(message: types.Message, state: FSMContext) -> None:
    await state.update_data(subject=message.text.strip())
    await message.answer("2-қадам: Сұрақ мәтінін жазыңыз:")
    await state.set_state(AddQuestionState.waiting_for_question)

@dp.message(AddQuestionState.waiting_for_question)
async def aq_question(message: types.Message, state: FSMContext) -> None:
    await state.update_data(question=message.text.strip())
    await message.answer(
        "3-қадам: 4 нұсқаны жазыңыз (әр нұсқа жаңа жолдан):\n\n"
        "_Мысалы:_\n"
        "Керей мен Жәнібек\n"
        "Қасым мен Хақназар\n"
        "Абылай мен Тәуке\n"
        "Есім мен Салқам",
        parse_mode="Markdown",
    )
    await state.set_state(AddQuestionState.waiting_for_options)

@dp.message(AddQuestionState.waiting_for_options)
async def aq_options(message: types.Message, state: FSMContext) -> None:
    opts = [o.strip() for o in message.text.strip().splitlines() if o.strip()]
    if len(opts) != 4:
        await message.answer("❌ Дәл 4 нұсқа жазыңыз (әр нұсқа жаңа жолдан).")
        return
    await state.update_data(options=opts)
    await message.answer(
        f"4-қадам: Дұрыс жауап нөмірін жазыңыз:\n\n"
        f"1 — {opts[0]}\n"
        f"2 — {opts[1]}\n"
        f"3 — {opts[2]}\n"
        f"4 — {opts[3]}"
    )
    await state.set_state(AddQuestionState.waiting_for_correct)

@dp.message(AddQuestionState.waiting_for_correct)
async def aq_correct(message: types.Message, state: FSMContext) -> None:
    try:
        correct = int(message.text.strip()) - 1
        if correct not in [0, 1, 2, 3]:
            raise ValueError
    except ValueError:
        await message.answer("❌ 1, 2, 3 немесе 4 санын ғана жазыңыз.")
        return

    data = await state.get_data()
    qid = add_question(
        subject=data["subject"],
        question=data["question"],
        options=data["options"],
        correct=correct,
        added_by=message.from_user.id,
    )
    opts = data["options"]

    await message.answer(
        f"✅ Сұрақ қосылды! (ID: {qid})\n\n"
        f"📚 Пән: *{data['subject']}*\n"
        f"❓ {data['question']}\n\n"
        f"A) {opts[0]}\n"
        f"B) {opts[1]}\n"
        f"C) {opts[2]}\n"
        f"D) {opts[3]}\n\n"
        f"✅ Дұрыс: {'ABCD'[correct]}) {opts[correct]}",
        parse_mode="Markdown",
    )
    await state.clear()
# ===========================================================================
# КУРАТОР ПАНЕЛЬ
# ===========================================================================

@dp.message(F.text == "🧑‍💼 Куратор панель")
async def curator_panel(message: types.Message) -> None:
    if not is_curator_only(message.from_user.id): return
    await message.answer("🧑‍💼 *Куратор панель*", reply_markup=curator_panel_kb(), parse_mode="Markdown")

@dp.callback_query(F.data == "cur_stats")
async def cur_stats(callback: types.CallbackQuery) -> None:
    students = get_curator_students(callback.from_user.id)
    await callback.message.answer(f"👥 Сіздің оқушыларыңыз: *{len(students)}* адам", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "cur_addtask")
async def cur_addtask(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("📝 Тапсырманың атын жазыңыз:")
    await state.set_state(CurTaskState.waiting_for_title)
    await callback.answer()

@dp.message(CurTaskState.waiting_for_title)
async def cur_task_title(message: types.Message, state: FSMContext) -> None:
    await state.update_data(title=message.text)
    await message.answer("🕒 Дедлайн: `ЖЖЖЖ-АА-КК СС:ММ`\nМысалы: `2025-06-15 18:00`", parse_mode="Markdown")
    await state.set_state(CurTaskState.waiting_for_deadline)

@dp.message(CurTaskState.waiting_for_deadline)
async def cur_task_deadline(message: types.Message, state: FSMContext) -> None:
    data     = await state.get_data()
    deadline = message.text.strip()
    try:
        datetime.strptime(deadline, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ Қате формат. Мысалы: `2025-06-15 18:00`", parse_mode="Markdown")
        return
    curator_id = message.from_user.id
    add_task(data["title"], deadline, curator_id=curator_id)
    students = get_curator_students(curator_id)
    sent = await broadcast_to(students, f"🔔 *Жаңа тапсырма қосылды!*\n📌 {data['title']}\n🕒 Дедлайн: {deadline}")
    await message.answer(
        f"✅ Тапсырма қосылды!\n📌 {data['title']}\n🕒 {deadline}\n\n📨 *{sent}* оқушыға хабар жіберілді.",
        parse_mode="Markdown",
    )
    await state.clear()

@dp.callback_query(F.data == "cur_broadcast")
async def cur_broadcast_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    students = get_curator_students(callback.from_user.id)
    if not students:
        await callback.answer("Сізде әлі оқушы жоқ.", show_alert=True)
        return
    await callback.message.answer(f"📢 Оқушыларыңызға (*{len(students)}* адам) хабар жазыңыз:", parse_mode="Markdown")
    await state.set_state(CurBroadcastState.waiting_for_message)
    await callback.answer()

@dp.message(CurBroadcastState.waiting_for_message)
async def cur_broadcast_send(message: types.Message, state: FSMContext) -> None:
    text = message.text or message.caption or ""
    if not text:
        await message.answer("⚠️ Мәтін жіберіңіз.")
        return
    students = get_curator_students(message.from_user.id)
    sent = await broadcast_to(students, f"📢 *Куратордан хабар:*\n\n{text}")
    await message.answer(f"✅ Хабар *{sent}* оқушыға жіберілді.", parse_mode="Markdown")
    await state.clear()

@dp.callback_query(F.data == "cur_addscore")
async def cur_addscore_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    students = get_curator_students(callback.from_user.id)
    if not students:
        await callback.answer("Сізде әлі оқушы жоқ.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👤 {uid}", callback_data=f"score_student_{uid}")]
        for uid in students
    ])
    await callback.message.answer("🏅 Балл қосылатын оқушыны таңдаңыз:", reply_markup=kb)
    await state.set_state(ScoreState.waiting_for_student)
    await callback.answer()

@dp.callback_query(ScoreState.waiting_for_student, F.data.startswith("score_student_"))
async def cur_addscore_pick(callback: types.CallbackQuery, state: FSMContext) -> None:
    student_id = int(callback.data.split("_")[2])
    await state.update_data(student_id=student_id)
    await callback.message.answer(f"✏️ `{student_id}` оқушысына қанша балл қосасыз?", parse_mode="Markdown")
    await state.set_state(ScoreState.waiting_for_score)
    await callback.answer()

@dp.message(ScoreState.waiting_for_score)
async def cur_addscore_save(message: types.Message, state: FSMContext) -> None:
    try:
        score = int(message.text.strip())
        if score <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Оң бүтін сан жазыңыз.")
        return
    data       = await state.get_data()
    student_id = data["student_id"]
    add_score(student_id, score)
    try:
        await bot.send_message(student_id, f"🏅 Куратор сізге *+{score} балл* қосты!", parse_mode="Markdown")
    except Exception:
        pass
    done, total, weekly = get_user_progress(student_id)
    await message.answer(
        f"✅ `{student_id}` оқушысына *+{score} балл* қосылды!\n\n"
        f"🏆 Жалпы: *{total}* | 🔥 Апталық: *{weekly}* | ✅ Тапсырмалар: *{done}*",
        parse_mode="Markdown",
    )
    await state.clear()

# ===========================================================================
# ГАЙД қосу (бас админ)
# ===========================================================================

@dp.message(Command("set_guide"))
async def cmd_set_guide(message: types.Message) -> None:
    if not is_main_admin(message.from_user.id): return
    await message.answer("📝 Қай пәнге гайд қосасыз?", reply_markup=subjects_kb("setguide"))

@dp.callback_query(F.data.startswith("setguide_"))
async def setguide_subject(callback: types.CallbackQuery, state: FSMContext) -> None:
    idx     = int(callback.data.split("_")[1])
    subject = SUBJECTS[idx]
    await state.update_data(subject=subject)
    await callback.message.answer(f"*{subject}* таңдалды.\n\nГайд мәтінін жазыңыз.", parse_mode="Markdown")
    await state.set_state(GuideState.waiting_for_content)
    await callback.answer()

@dp.message(GuideState.waiting_for_content)
async def save_guide(message: types.Message, state: FSMContext) -> None:
    data    = await state.get_data()
    subject = data["subject"]
    text    = message.html_text or message.caption or ""
    file_id = None
    if message.document:
        file_id = message.document.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id
    if not text and not file_id:
        await message.answer("⚠️ Мәтін немесе файл жіберіңіз.")
        return
    set_guide(subject, text, file_id)
    await message.answer(f"✅ *{subject}* гайды сақталды!", parse_mode="Markdown")
    await state.clear()

# ===========================================================================
# КІТАП қосу / жою
# ===========================================================================

@dp.message(Command("add_book"))
async def cmd_add_book(message: types.Message) -> None:
    if not is_main_admin(message.from_user.id): return
    await message.answer("📚 Қай пәнге кітап қосасыз?", reply_markup=subjects_kb("addbook"))

@dp.callback_query(F.data.startswith("addbook_"))
async def addbook_subject(callback: types.CallbackQuery, state: FSMContext) -> None:
    idx     = int(callback.data.split("_")[1])
    subject = SUBJECTS[idx]
    await state.update_data(subject=subject)
    await callback.message.answer(f"*{subject}* таңдалды.\nКітаптың *атын* жазыңыз:", parse_mode="Markdown")
    await state.set_state(BookState.waiting_for_title)
    await callback.answer()

@dp.message(BookState.waiting_for_title)
async def book_title_received(message: types.Message, state: FSMContext) -> None:
    await state.update_data(title=message.text)
    await message.answer("Енді кітаптың *файлын* (PDF/DOC) жіберіңіз:", parse_mode="Markdown")
    await state.set_state(BookState.waiting_for_file)

@dp.message(BookState.waiting_for_file, F.document)
async def book_file_received(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    add_book_to_db(data["subject"], data["title"], message.document.file_id)
    await message.answer(f"✅ *{data['title']}* кітабы сақталды!", parse_mode="Markdown")
    await state.clear()

@dp.message(Command("delete_book"))
async def cmd_delete_book(message: types.Message) -> None:
    if not is_main_admin(message.from_user.id): return
    await message.answer("🗑 Қай пәннің кітабын жоясыз?", reply_markup=subjects_kb("delbook"))

@dp.callback_query(F.data.startswith("delbook_"))
async def delbook_subject(callback: types.CallbackQuery) -> None:
    idx     = int(callback.data.split("_")[1])
    subject = SUBJECTS[idx]
    books   = get_books(subject)
    if not books:
        await callback.answer("Бұл пәнде кітаптар жоқ.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑 {row['title']}", callback_data=f"confirmdelete_{row['id']}")]
        for row in books
    ])
    await callback.message.answer(f"*{subject}* — жойылатын кітапты таңдаңыз:", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("confirmdelete_"))
async def confirm_delete_book(callback: types.CallbackQuery) -> None:
    book_id = int(callback.data.split("_")[1])
    delete_book_from_db(book_id)
    await callback.message.answer("✅ Кітап жойылды.")
    await callback.answer()

# ===========================================================================
# ТАПСЫРМА қосу / жою (бас админ)
# ===========================================================================

@dp.message(Command("add_task", "addtask"))
async def cmd_add_task(message: types.Message, state: FSMContext) -> None:
    if not is_main_admin(message.from_user.id): return
    await message.answer("📝 Жаңа тапсырманың атын жазыңыз:")
    await state.set_state(TaskState.waiting_for_title)

@dp.message(TaskState.waiting_for_title)
async def task_title(message: types.Message, state: FSMContext) -> None:
    await state.update_data(title=message.text)
    await message.answer("🕒 Дедлайн: `ЖЖЖЖ-АА-КК СС:ММ`", parse_mode="Markdown")
    await state.set_state(TaskState.waiting_for_deadline)

@dp.message(TaskState.waiting_for_deadline)
async def task_deadline(message: types.Message, state: FSMContext) -> None:
    data     = await state.get_data()
    deadline = message.text.strip()
    try:
        datetime.strptime(deadline, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ Қате формат. Мысалы: `2025-06-15 18:00`", parse_mode="Markdown")
        return
    add_task(data["title"], deadline, curator_id=None)
    await message.answer(f"✅ Тапсырма қосылды!\n📌 {data['title']}\n🕒 {deadline}")
    await broadcast_all(f"🔔 *Жаңа тапсырма қосылды!*\n📌 {data['title']}\n🕒 Дедлайн: {deadline}")
    await state.clear()

@dp.callback_query(F.data.startswith("deltask_"))
async def do_delete_task(callback: types.CallbackQuery) -> None:
    task_id = int(callback.data.split("_")[1])
    ok = delete_task(task_id)
    if ok:
        await callback.message.answer("✅ Тапсырма жойылды.")
    else:
        await callback.answer("Тапсырма табылмады.", show_alert=True)
    await callback.answer()

@dp.message(Command("delete_task"))
async def cmd_delete_task(message: types.Message) -> None:
    if not is_main_admin(message.from_user.id): return
    tasks = get_active_tasks()
    if not tasks:
        await message.answer("Тапсырмалар жоқ.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"❌ {t['title']}", callback_data=f"deltask_{t['id']}")]
        for t in tasks
    ])
    await message.answer("Жойылатын тапсырманы таңдаңыз:", reply_markup=kb)

# ===========================================================================
# ХАБАР ТАРАТУ (бас админ)
# ===========================================================================

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, state: FSMContext) -> None:
    if not is_main_admin(message.from_user.id): return
    await message.answer("📢 Барлық студенттерге жіберілетін хабарды жазыңыз:")
    await state.set_state(BroadcastState.waiting_for_message)

@dp.message(BroadcastState.waiting_for_message)
async def do_broadcast(message: types.Message, state: FSMContext) -> None:
    text = message.text or message.caption or ""
    if not text:
        await message.answer("⚠️ Мәтін жіберіңіз.")
        return
    sent = await broadcast_all(f"📢 *Жаңа хабарлама:*\n\n{text}")
    await message.answer(f"✅ Хабар *{sent}* пайдаланушыға жіберілді.", parse_mode="Markdown")
    await state.clear()

# ===========================================================================
# КУРАТОР қосу / жою (бас админ)
# ===========================================================================

@dp.message(Command("add_curator"))
async def cmd_add_curator(message: types.Message, state: FSMContext) -> None:
    if not is_main_admin(message.from_user.id): return
    await message.answer("👤 Жаңа куратордың Telegram *ID-ін* жазыңыз:", parse_mode="Markdown")
    await state.set_state(CuratorState.waiting_for_add_id)

@dp.message(CuratorState.waiting_for_add_id)
async def save_curator(message: types.Message, state: FSMContext) -> None:
    try:
        cid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Сан форматында ID жазыңыз.")
        return
    code = add_curator(cid)
    await message.answer(
        f"✅ Куратор қосылды!\n\n🆔 ID: `{cid}`\n🔑 Код: `{code}`",
        parse_mode="Markdown",
    )
    await state.clear()

@dp.callback_query(F.data.startswith("delcurator_"))
async def do_remove_curator(callback: types.CallbackQuery) -> None:
    if not is_main_admin(callback.from_user.id):
        await callback.answer("Тек бас админ орындай алады.", show_alert=True)
        return
    cid = int(callback.data.split("_")[1])
    ok  = remove_curator(cid)
    if ok:
        await callback.message.answer(f"✅ `{cid}` куратордан алынды.", parse_mode="Markdown")
    else:
        await callback.answer("Куратор табылмады.", show_alert=True)
    await callback.answer()

@dp.message(Command("list_curators"))
async def cmd_list_curators(message: types.Message) -> None:
    if not is_main_admin(message.from_user.id): return
    curators = get_curators()
    if not curators:
        await message.answer("Кураторлар жоқ.")
        return
    lines = [f"• `{row['id']}` — {len(get_curator_students(row['id']))} оқушы" for row in curators]
    await message.answer("🧑‍💼 *Кураторлар тізімі:*\n\n" + "\n".join(lines), parse_mode="Markdown")

# ===========================================================================
# ДЕДЛАЙН ЕСКЕРТУ ЦИКЛЫ
# ===========================================================================
NOTIFY_HOURS = [24, 12, 3]

async def deadline_notifier() -> None:
    while True:
        for task in get_active_tasks():
            deadline_dt = datetime.strptime(task["deadline"], "%Y-%m-%d %H:%M")
            hours_left  = (deadline_dt - datetime.now()).total_seconds() / 3600
            for h in NOTIFY_HOURS:
                label = str(h)
                if 0 < hours_left <= h and not was_notified(task["id"], label):
                    mark_task_notified(task["id"], label)
                    text = (
                        f"⚠️ *ЕСКЕРТУ!*\n"
                        f"📌 _{task['title']}_ тапсырмасының дедлайнына *{h} сағат* қалды!"
                    )
                    if task["curator_id"]:
                        await broadcast_to(get_curator_students(task["curator_id"]), text)
                    else:
                        await broadcast_all(text)
        await asyncio.sleep(3600)

# ===========================================================================
# ІСКЕ ҚОСУ
# ===========================================================================

async def daily_challenge_scheduler() -> None:
    """Күн сайын 09:00-де Daily Challenge жіберу."""
    questions = []
    try:
        from questions import QUESTIONS  # optional local seed
        questions = QUESTIONS
    except ImportError:
        questions = []
    # Бастапқы сұрақтарды базаға жүктеу (тек бір рет)
    if get_question_count() == 0 and questions:
        for q in questions:
            add_question(
                subject=q["subject"],
                question=q["q"],
                options=q["a"],
                correct=q["correct"],
            )

    while True:
        now = datetime.now()
        # Келесі 09:00-ді есептеу
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target + timedelta(days=1)
        wait_seconds = max((target - now).total_seconds(), 0)
        await asyncio.sleep(wait_seconds)
        await send_daily_challenge_to_all()


async def main() -> None:
    init_db()
    asyncio.create_task(deadline_notifier())
    asyncio.create_task(daily_challenge_scheduler())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
