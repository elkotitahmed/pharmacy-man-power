import streamlit as st
import pandas as pd
import sqlite3
import calendar
from datetime import datetime
import io
import hashlib

st.set_page_config(page_title="نظام إدارة الصيادلة", layout="wide")

# ------------------- دوال التوقيت بصيغة 12 ساعة -------------------
def generate_time_options():
    options = []
    for hour in range(1, 13):
        for minute in [0]:  # يمكن إضافة 30 للدقة نصف ساعة
            for ampm in ['AM', 'PM']:
                options.append(f"{hour:02d}:{minute:02d} {ampm}")
    # ترتيب زمني صحيح
    def time_key(t):
        h = int(t.split(':')[0])
        m = int(t.split(':')[1].split()[0])
        ampm = t.split()[1]
        if ampm == 'AM':
            return (h % 12), m
        else:
            return (h % 12) + 12, m
    options.sort(key=time_key)
    return options

TIME_OPTIONS = generate_time_options()

def convert_12h_to_24h(time_str):
    if not time_str:
        return None
    try:
        parts = time_str.split()
        time_part = parts[0]
        ampm = parts[1]
        hh, mm = map(int, time_part.split(':'))
        if ampm == 'AM':
            if hh == 12:
                hh = 0
        else:
            if hh != 12:
                hh += 12
        return hh + mm / 60.0
    except:
        return None

def calculate_net_hours(start_12h, end_12h):
    if not start_12h or not end_12h:
        return 0.0
    start_h = convert_12h_to_24h(start_12h)
    end_h = convert_12h_to_24h(end_12h)
    if start_h is None or end_h is None:
        return 0.0
    diff = end_h - start_h
    if diff < 0:
        diff += 24
    return round(diff, 2)

# ------------------- دوال قاعدة البيانات -------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS employees
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  name TEXT,
                  monthly_rate REAL,
                  is_admin INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  employee_id INTEGER,
                  year INTEGER,
                  month INTEGER,
                  day INTEGER,
                  check_in TEXT,
                  check_out TEXT,
                  net_hours REAL,
                  notes TEXT,
                  FOREIGN KEY(employee_id) REFERENCES employees(id))''')
    admin_exists = c.execute("SELECT * FROM employees WHERE username='admin'").fetchone()
    if not admin_exists:
        c.execute("INSERT INTO employees (username, password, name, monthly_rate, is_admin) VALUES (?,?,?,?,?)",
                  ('admin', hash_password('admin123'), 'صاحب الصيدلية', 750.0, 1))
    conn.commit()
    conn.close()

init_db()

def login(username, password):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    user = c.execute("SELECT * FROM employees WHERE username=? AND password=?", (username, hash_password(password))).fetchone()
    conn.close()
    if user:
        return {'id': user[0], 'username': user[1], 'name': user[3], 'monthly_rate': user[4], 'is_admin': user[5]}
    return None

def get_workdays(year, month):
    cal = calendar.monthcalendar(year, month)
    workdays = []
    for week in cal:
        for day in week:
            if day != 0:
                date = datetime(year, month, day)
                if date.weekday() != 4:
                    workdays.append(date)
    return workdays

def get_attendance(employee_id, year, month):
    conn = sqlite3.connect('pharmacy.db')
    df = pd.read_sql_query("SELECT day, check_in, check_out, net_hours, notes FROM attendance WHERE employee_id=? AND year=? AND month=? ORDER BY day",
                           conn, params=(employee_id, year, month))
    conn.close()
    return df

def save_attendance(employee_id, year, month, day, check_in, check_out, net_hours, notes):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE employee_id=? AND year=? AND month=? AND day=?", (employee_id, year, month, day))
    c.execute("INSERT INTO attendance (employee_id, year, month, day, check_in, check_out, net_hours, notes) VALUES (?,?,?,?,?,?,?,?)",
              (employee_id, year, month, day, check_in, check_out, net_hours, notes))
    conn.commit()
    conn.close()

def delete_month_attendance(employee_id, year, month):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE employee_id=? AND year=? AND month=?", (employee_id, year, month))
    conn.commit()
    conn.close()

def get_employees():
    conn = sqlite3.connect('pharmacy.db')
    df = pd.read_sql_query("SELECT id, username, name, monthly_rate, is_admin FROM employees", conn)
    conn.close()
    return df

def add_employee(username, password, name, monthly_rate, is_admin=0):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO employees (username, password, name, monthly_rate, is_admin) VALUES (?,?,?,?,?)",
                  (username, hash_password(password), name, monthly_rate, is_admin))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_monthly_rate(employee_id, new_rate):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    c.execute("UPDATE employees SET monthly_rate=? WHERE id=?", (new_rate, employee_id))
    conn.commit()
    conn.close()

def delete_employee(employee_id):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE employee_id=?", (employee_id,))
    c.execute("DELETE FROM employees WHERE id=?", (employee_id,))
    conn.commit()
    conn.close()

# ------------------- جلسة المستخدم -------------------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

if not st.session_state.logged_in:
    st.title("تسجيل الدخول")
    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        user = login(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.rerun()
        else:
            st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

user = st.session_state.user

# ------------------- الشريط الجانبي -------------------
with st.sidebar:
    st.header(f"مرحبًا {user['name']}")
    if st.button("تسجيل خروج"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    if user['is_admin']:
        st.subheader("إدارة الموظفين")
        employees_df = get_employees()
        st.dataframe(employees_df[['id', 'username', 'name', 'monthly_rate']], use_container_width=True)
        
        with st.expander("إضافة موظف جديد"):
            new_username = st.text_input("اسم المستخدم")
            new_password = st.text_input("كلمة المرور", type="password")
            new_name = st.text_input("الاسم")
            new_rate = st.number_input("سعر الساعة الشهرية (جنيه)", min_value=0.0, value=750.0)
            if st.button("إضافة"):
                if add_employee(new_username, new_password, new_name, new_rate):
                    st.success("تمت الإضافة")
                    st.rerun()
                else:
                    st.error("اسم المستخدم موجود بالفعل")
        
        with st.expander("تعديل سعر الساعة"):
            emp_id = st.number_input("معرف الموظف", min_value=1, step=1)
            new_rate = st.number_input("السعر الجديد", min_value=0.0)
            if st.button("تحديث"):
                update_monthly_rate(emp_id, new_rate)
                st.success("تم التحديث")
                st.rerun()
        
        with st.expander("حذف موظف"):
            emp_id = st.number_input("معرف الموظف للحذف", min_value=1, step=1)
            if st.button("حذف"):
                delete_employee(emp_id)
                st.success("تم الحذف")
                st.rerun()

# ------------------- محتوى التطبيق -------------------
st.title("نظام الحضور وحساب الراتب")

current_year = datetime.now().year
year = st.sidebar.selectbox("السنة", options=range(2020, 2031), index=current_year-2020)
month = st.sidebar.selectbox("الشهر", options=range(1,13), format_func=lambda x: calendar.month_name[x])

if user['is_admin']:
    employees = get_employees()
    employee_options = {emp['id']: emp['name'] for emp in employees.to_dict('records')}
    selected_employee_id = st.sidebar.selectbox("اختر الموظف", options=list(employee_options.keys()), format_func=lambda x: employee_options[x])
    monthly_rate = employees[employees['id'] == selected_employee_id]['monthly_rate'].values[0]
else:
    selected_employee_id = user['id']
    monthly_rate = user['monthly_rate']

contract_hours = st.sidebar.number_input("عدد الساعات اليومية المتعاقد عليها", min_value=1, max_value=24, value=8, step=1)
paid_leave_keyword = st.sidebar.text_input("كلمة الإجازة المدفوعة", value="إجازة مدفوعة")
start_time_info = st.sidebar.selectbox("من الساعة (توجيهي فقط)", options=TIME_OPTIONS, index=9)  # 09:00 AM
end_time_info = st.sidebar.selectbox("إلى الساعة (توجيهي فقط)", options=TIME_OPTIONS, index=17) # 05:00 PM

st.markdown(f"**العمل المتعاقد عليه من {start_time_info} إلى {end_time_info} ({contract_hours} ساعة يومياً)**")

workdays = get_workdays(year, month)
attendance_df = get_attendance(selected_employee_id, year, month)

days_list = []
for d in workdays:
    day_num = d.day
    row = attendance_df[attendance_df['day'] == day_num]
    if not row.empty:
        days_list.append({
            'اليوم': day_num,
            'التاريخ': d.strftime("%Y-%m-%d"),
            'اسم اليوم': d.strftime("%A"),
            'وقت الحضور': row.iloc[0]['check_in'] if pd.notna(row.iloc[0]['check_in']) else "",
            'وقت الانصراف': row.iloc[0]['check_out'] if pd.notna(row.iloc[0]['check_out']) else "",
            'صافي (ساعات)': row.iloc[0]['net_hours'] if pd.notna(row.iloc[0]['net_hours']) else 0.0,
            'الملاحظات': row.iloc[0]['notes'] if pd.notna(row.iloc[0]['notes']) else ""
        })
    else:
        days_list.append({
            'اليوم': day_num,
            'التاريخ': d.strftime("%Y-%m-%d"),
            'اسم اليوم': d.strftime("%A"),
            'وقت الحضور': "",
            'وقت الانصراف': "",
            'صافي (ساعات)': 0.0,
            'الملاحظات': ""
        })

df = pd.DataFrame(days_list)

# عرض الجدول مع Selectbox للأوقات
if user['is_admin']:
    edited_df = st.data_editor(
        df,
        column_config={
            "اليوم": st.column_config.NumberColumn("اليوم", disabled=True),
            "التاريخ": st.column_config.TextColumn("التاريخ", disabled=True),
            "اسم اليوم": st.column_config.TextColumn("اسم اليوم", disabled=True),
            "وقت الحضور": st.column_config.SelectboxColumn(
                "وقت الحضور",
                options=TIME_OPTIONS,
                required=False
            ),
            "وقت الانصراف": st.column_config.SelectboxColumn(
                "وقت الانصراف",
                options=TIME_OPTIONS,
                required=False
            ),
            "صافي (ساعات)": st.column_config.NumberColumn("صافي (ساعات)", disabled=True, format="%.2f"),
            "الملاحظات": st.column_config.TextColumn("الملاحظات")
        },
        use_container_width=True,
        num_rows="fixed"
    )
    # تحديث الصافي
    for idx, row in edited_df.iterrows():
        net = calculate_net_hours(row["وقت الحضور"], row["وقت الانصراف"])
        edited_df.at[idx, "صافي (ساعات)"] = net
    # حفظ البيانات
    delete_month_attendance(selected_employee_id, year, month)
    for _, row in edited_df.iterrows():
        save_attendance(selected_employee_id, year, month, row["اليوم"],
                        row["وقت الحضور"], row["وقت الانصراف"], row["صافي (ساعات)"], row["الملاحظات"])
    st.success("تم حفظ التغييرات")
else:
    st.dataframe(df, use_container_width=True)
    st.info("هذا جدول الحضور الخاص بك. للاستفسار، تواصل مع المدير.")

# ------------------- حسابات الراتب -------------------
actual_hours = df["صافي (ساعات)"].sum()
paid_leave_days = df[df["الملاحظات"].astype(str).str.contains(paid_leave_keyword, na=False)].shape[0]
considered_hours = actual_hours + (paid_leave_days * contract_hours)
working_days = len(workdays)

if working_days > 0:
    actual_hour_rate = monthly_rate / working_days
    salary = considered_hours * actual_hour_rate
else:
    actual_hour_rate = 0
    salary = 0

st.divider()
col1, col2, col3, col4 = st.columns(4)
col1.metric("📅 عدد أيام العمل", working_days)
col2.metric("⏱️ الساعات الفعلية", f"{actual_hours:.2f}")
col3.metric("📝 أيام إجازة مدفوعة", paid_leave_days)
col4.metric("💰 الساعات المعتبرة", f"{considered_hours:.2f}")
st.metric("💵 الراتب المستحق (جنيه)", f"{salary:.2f}")

st.markdown(f"""
**شرح الحساب:**  
- أجر الساعة الفعلي = {monthly_rate} / {working_days} = {actual_hour_rate:.2f} جنيه  
- الساعات المعتبرة = {actual_hours:.2f} + {paid_leave_days}×{contract_hours} = {considered_hours:.2f}  
- الراتب = {considered_hours:.2f} × {actual_hour_rate:.2f} = {salary:.2f} جنيه
""")

# ------------------- جدول ملون -------------------
def color_rows(row):
    notes = str(row["الملاحظات"]) if pd.notna(row["الملاحظات"]) else ""
    if paid_leave_keyword in notes:
        return ["background-color: #fff3cd"] * len(row)
    elif (row["وقت الحضور"] == "" or row["وقت الانصراف"] == "") and row["صافي (ساعات)"] == 0:
        return ["background-color: #f8d7da"] * len(row)
    else:
        return [""] * len(row)

styled_summary = df.style.apply(color_rows, axis=1).format({"صافي (ساعات)": "{:.2f}"})
st.subheader("📊 ملخص الجدول (مع تلوين الأيام)")
st.dataframe(styled_summary, use_container_width=True)

# ------------------- تصدير -------------------
st.divider()
csv = df.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 تحميل كـ CSV", data=csv,
                   file_name=f"attendance_{selected_employee_id}_{year}_{month}.csv", mime="text/csv")
output = io.BytesIO()
with pd.ExcelWriter(output, engine='openpyxl') as writer:
    df.to_excel(writer, index=False, sheet_name="الحضور")
st.download_button("📊 تحميل كـ Excel", data=output.getvalue(),
                   file_name=f"attendance_{selected_employee_id}_{year}_{month}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
