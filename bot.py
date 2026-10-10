import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pandas as pd
from datetime import datetime
import os

TOKEN = '8795865331:AAHRdkD5VWGPdN9NA0-VznLsPZ5Kt1oOTrk' # ضع مفتاح البوت هنا
bot = telebot.TeleBot(TOKEN)

# اسم ملف الإكسل الذي سيسحب منه البوت البيانات (يجب أن يكون في نفس المجلد)
EXCEL_FILE = "مسائي 1 الكورس الاول.xlsx"

# نعرض 60 اسم في كل رسالة (صفحة) لتجنب حدود تليجرام التي تمنع أكثر من 100 زر
STUDENTS_PER_PAGE = 60  

SUBJECTS_DICT = {}
STUDENTS_LIST = []

def load_data():
    global SUBJECTS_DICT, STUDENTS_LIST
    try:
        # قراءة المواد والمدرسين من شيت تعريف المواد
        df_subj = pd.read_excel(EXCEL_FILE, sheet_name='تعريف المواد', header=None)
        SUBJECTS_DICT.clear()
        for i in range(4, len(df_subj)):
            subj = str(df_subj.iloc[i, 1]).strip()
            teacher = str(df_subj.iloc[i, 2]).strip()
            if subj and subj != 'nan':
                SUBJECTS_DICT[subj] = teacher if teacher != 'nan' else 'غير محدد'
                
        # قراءة أسماء الطلاب من شيت تعريف الاسماء
        df_names = pd.read_excel(EXCEL_FILE, sheet_name='تعريف الاسماء', header=None)
        STUDENTS_LIST.clear()
        for i in range(2, len(df_names)):
            name = str(df_names.iloc[i, 1]).strip()
            if name and name != 'nan' and len(name) > 3:
                STUDENTS_LIST.append(name)
                
    except Exception as e:
        print(f"حدث خطأ أثناء قراءة الملف: {e}")

# تحميل البيانات عند تشغيل البوت
load_data()
session_data = {}

@bot.message_handler(commands=['start'])
def start_bot(message):
    chat_id = message.chat.id
    load_data() # تحديث البيانات من الملف في كل مرة تبدأ فيها الجلسة
    
    session_data[chat_id] = {'subject': None, 'teacher': None, 'absent_students': set(), 'page': 0}
    
    markup = InlineKeyboardMarkup(row_width=1)
    if not SUBJECTS_DICT:
        bot.send_message(chat_id, "⚠️ لم أتمكن من العثور على بيانات المواد. تأكد من وجود ملف الإكسل بنفس المجلد.")
        return
         
    for idx, subj in enumerate(SUBJECTS_DICT.keys()):
        markup.add(InlineKeyboardButton(subj, callback_data=f"subj_{idx}"))
        
    bot.send_message(chat_id, "📚 أهلاً بك أبو أسد! يرجى اختيار المادة لبدء تسجيل الغياب:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('subj_'))
def handle_subject_selection(call):
    chat_id = call.message.chat.id
    subj_idx = int(call.data.split('_')[1])
    subj = list(SUBJECTS_DICT.keys())[subj_idx]
    teacher = SUBJECTS_DICT[subj]
    
    session_data[chat_id]['subject'] = subj
    session_data[chat_id]['teacher'] = teacher
    session_data[chat_id]['page'] = 0
    
    send_students_list(chat_id, call.message.message_id)

def send_students_list(chat_id, message_id=None):
    absent_students = session_data[chat_id]['absent_students']
    subj = session_data[chat_id]['subject']
    teacher = session_data[chat_id]['teacher']
    page = session_data[chat_id]['page']
    
    markup = InlineKeyboardMarkup(row_width=2)
    
    start_idx = page * STUDENTS_PER_PAGE
    end_idx = min(start_idx + STUDENTS_PER_PAGE, len(STUDENTS_LIST))
    
    buttons = []
    for i in range(start_idx, end_idx):
        student = STUDENTS_LIST[i]
        # إضافة دائرة حمراء للاسم إذا كان غائباً
        btn_text = f"🔴 {student}" if i in absent_students else student
        buttons.append(InlineKeyboardButton(btn_text, callback_data=f"toggle_{i}"))
        
    # عرض كل اسمين في سطر واحد
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i+1])
        else:
            markup.add(buttons[i])
            
    # أزرار التنقل بين الصفحات
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ الصفحة السابقة", callback_data="prev_page"))
    if end_idx < len(STUDENTS_LIST):
        nav_buttons.append(InlineKeyboardButton("الصفحة التالية ➡️", callback_data="next_page"))
    
    if nav_buttons:
        markup.add(*nav_buttons)
        
    # زر الحفظ والإنهاء
    markup.add(InlineKeyboardButton("💾 حفظ وإنهاء التسجيل (إنشاء إكسل) 💾", callback_data="finish"))
    
    total_pages = (len(STUDENTS_LIST) + STUDENTS_PER_PAGE - 1) // STUDENTS_PER_PAGE
    text = f"📚 **المادة:** {subj}\n👨‍🏫 **المدرس:** {teacher}\n" \
           f"📄 **الأسماء (صفحة {page + 1} من {total_pages}):**\n\n" \
           f"👈 **اختر أسماء الطلاب الغائبين فقط** (سيظهر بجانبهم 🔴).\n" \
           f"👈 تنقل بين الصفحات، وعند الانتهاء تماماً اضغط حفظ وإنهاء."
           
    if message_id:
        bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_'))
def handle_toggle(call):
    chat_id = call.message.chat.id
    if chat_id not in session_data:
        bot.answer_callback_query(call.id, "انتهت الجلسة. أرسل /start من جديد.")
        return
        
    student_idx = int(call.data.split('_')[1])
    absent_students = session_data[chat_id]['absent_students']
    
    # تبديل الحالة بين الحضور والغياب
    if student_idx in absent_students:
        absent_students.remove(student_idx)
    else:
        absent_students.add(student_idx)
        
    # تحديث اللوحة فوراً بعد الاختيار
    send_students_list(chat_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data in ['next_page', 'prev_page'])
def handle_pagination(call):
    chat_id = call.message.chat.id
    if chat_id not in session_data:
        bot.answer_callback_query(call.id, "الجلسة منتهية.")
        return
        
    if call.data == 'next_page':
        session_data[chat_id]['page'] += 1
    else:
        session_data[chat_id]['page'] -= 1
        
    send_students_list(chat_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'finish')
def handle_finish(call):
    chat_id = call.message.chat.id
    if chat_id not in session_data:
        bot.answer_callback_query(call.id, "الجلسة منتهية.")
        return
        
    bot.edit_message_text("⏳ جاري سحب البيانات وإنشاء ملف الإكسل للغيابات...", chat_id=chat_id, message_id=call.message.message_id)
    
    absent_indices = session_data[chat_id]['absent_students']
    subj = session_data[chat_id]['subject']
    teacher = session_data[chat_id]['teacher']
    
    records = []
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    for i, student in enumerate(STUDENTS_LIST):
        status = "غائب" if i in absent_indices else "حاضر"
        records.append({
            "ت": i + 1,
            "اسم الطالب": student,
            "الحالة": status,
            "التاريخ": current_date,
            "المادة": subj,
            "المدرس": teacher
        })
        
    df = pd.DataFrame(records)
    file_name = f"Attendance_{datetime.now().strftime('%H%M%S')}.xlsx"
    df.to_excel(file_name, index=False)
    
    with open(file_name, 'rb') as file:
        bot.send_document(
            chat_id, 
            file, 
            caption=f"✅ تم الانتهاء بنجاح!\n\n📚 **المادة:** {subj}\n👨‍🏫 **المدرس:** {teacher}\n❌ **عدد الغائبين:** {len(absent_indices)}\n\nإليك ملف الإكسل الجاهز.", 
            parse_mode='Markdown'
        )
        
    os.remove(file_name)
    del session_data[chat_id]

if __name__ == '__main__':
    print("البوت يعمل الآن ومربوط بملف الإكسل...")
    bot.polling(none_stop=True)