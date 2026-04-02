import streamlit as st
import pandas as pd
import sqlite3
import calendar
from datetime import datetime
import io
import hashlib

# إعداد الصفحة
st.set_page_config(page_title="نظام إدارة الصيادلة", layout="wide")

# دالة لتوليد هاش لكلمة المرور (للتخزين الآمن)
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# دالة لتهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    # جدول الموظفين
    c.execute('''CREATE TABLE IF NOT EXISTS employees
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  name TEXT,
                  monthly_rate REAL,
                  is_admin INTEGER)''')
    # جدول الحضور
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
    # إضافة مدير افتراضي إذا لم يكن موجودًا
    admin_exists = c.execute("SELECT * FROM employees WHERE username='admin'").fetchone()
    if not admin_exists:
        c.execute("INSERT INTO employees (username, password, name, monthly_rate, is_admin) VALUES (?,?,?,?,?)",
                  ('admin', hash_password('admin123'), 'صاحب الصيدلية', 750.0, 1))
    conn.commit()
    conn.close()

init_db()

# دالة للتحقق من تسجيل الدخول
def login(username, password):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    user = c.execute("SELECT * FROM employees WHERE username=? AND password=?", (username, hash_password(password))).fetchone()
    conn.close()
    if user:
        return {'id': user[0], 'username': user[1], 'name': user[3], 'monthly_rate': user[4], 'is_admin': user[5]}
    return None

# دالة للحصول على أيام العمل في شهر معين (عدا الجمعة)
def get_workdays(year, month):
    cal = calendar.monthcalendar(year, month)
    workdays = []
    for week in cal:
        for day in week:
            if day != 0:
                date = datetime(year, month, day)
                if date.weekday() != 4:  # 4 = Friday
                    workdays.append(date)
    return workdays

# دالة لحساب الصافي من ساعتين
def calculate_net_hours(start, end):
    if not start or not end:
        return 0.0
    try:
        start_dt = datetime.strptime(start, "%H:%M")
        end_dt = datetime.strptime(end, "%H:%M")
        diff = end_dt - start_dt
        return round(diff.total_seconds() / 3600, 2)
    except:
        return 0.0

# دالة لجلب بيانات الحضور لموظف في شهر معين
def get_attendance(employee_id, year, month):
    conn = sqlite3.connect('pharmacy.db')
    df = pd.read_sql_query("SELECT day, check_in, check_out, net_hours, notes FROM attendance WHERE employee_id=? AND year=? AND month=? ORDER BY day",
                           conn, params=(employee_id, year, month))
    conn.close()
    return df

# دالة لحفظ بيانات الحضور (استبدال أو إدراج)
def save_attendance(employee_id, year, month, day, check_in, check_out, net_hours, notes):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE employee_id=? AND year=? AND month=? AND day=?", (employee_id, year, month, day))
    c.execute("INSERT INTO attendance (employee_id, year, month, day, check_in, check_out, net_hours, notes) VALUES (?,?,?,?,?,?,?,?)",
              (employee_id, year, month, day, check_in, check_out, net_hours, notes))
    conn.commit()
    conn.close()

# دالة لحذف كل بيانات شهر لموظف (عند تغيير الشهر)
def delete_month_attendance(employee_id, year, month):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE employee_id=? AND year=? AND month=?", (employee_id, year, month))
    conn.commit()
    conn.close()

# دالة للحصول على قائمة الموظفين (للمدير)
def get_employees():
    conn = sqlite3.connect('pharmacy.db')
    df = pd.read_sql_query("SELECT id, username, name, monthly_rate, is_admin FROM employees", conn)
    conn.close()
    return df

# دالة لإضافة موظف جديد
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

# دالة لتحديث سعر الساعة الشهرية للموظف
def update_monthly_rate(employee_id, new_rate):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    c.execute("UPDATE employees SET monthly_rate=? WHERE id=?", (new_rate, employee_id))
    conn.commit()
    conn.close()

# دالة لحذف موظف (وكل حضوره)
def delete_employee(employee_id):
    conn = sqlite3.connect('pharmacy.db')
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE employee_id=?", (employee_id,))
    c.execute("DELETE FROM employees WHERE id=?", (employee_id,))
    conn.commit()
    conn.close()

# جلسة المستخدم
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# صفحة تسجيل الدخول
if not st.session_state.logged_in:
    st.title("تسجيل الدخول")
    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        user = login(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.experimental_rerun()
        else:
            st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

# -------------------------------
# التطبيق بعد تسجيل الدخول
# -------------------------------
user = st.session_state.user

# شريط جانبي للمستخدم والإعدادات
with st.sidebar:
    st.header(f"مرحبًا {user['name']}")
    if st.button("تسجيل خروج"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.experimental_rerun()

    if user['is_admin']:
        st.subheader("إدارة الموظفين")
        # عرض قائمة الموظفين
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
                    st.experimental_rerun()
                else:
                    st.error("اسم المستخدم موجود بالفعل")
        
        with st.expander("تعديل سعر الساعة"):
            emp_id = st.number_input("معرف الموظف", min_value=1, step=1)
            new_rate = st.number_input("السعر الجديد", min_value=0.0)
            if st.button("تحديث"):
                update_monthly_rate(emp_id, new_rate)
                st.success("تم التحديث")
                st.experimental_rerun()
        
        with st.expander("حذف موظف"):
            emp_id = st.number_input("معرف الموظف للحذف", min_value=1, step=1)
            if st.button("حذف"):
                delete_employee(emp_id)
                st.success("تم الحذف")
                st.experimental_rerun()

# محتوى التطبيق الأساسي
st.title("نظام الحضور وحساب الراتب")

# اختيار الشهر
current_year = datetime.now().year
year = st.sidebar.selectbox("السنة", options=range(2020, 2031), index=current_year-2020)
month = st.sidebar.selectbox("الشهر", options=range(1,13), format_func=lambda x: calendar.month_name[x])

# إذا كان المستخدم مديرًا، يمكنه اختيار الموظف
if user['is_admin']:
    employees = get_employees()
    employees_list = employees[['id', 'name']].to_dict('records')
    employee_options = {emp['id']: emp['name'] for emp in employees_list}
    selected_employee_id = st.sidebar.selectbox("اختر الموظف", options=list(employee_options.keys()), format_func=lambda x: employee_options[x])
    # سعر الساعة الشهرية لهذا الموظف
    monthly_rate = employees[employees['id'] == selected_employee_id]['monthly_rate'].values[0]
else:
    selected_employee_id = user['id']
    monthly_rate = user['monthly_rate']

# معلومات إضافية
contract_hours = st.sidebar.number_input("عدد الساعات اليومية المتعاقد عليها", min_value=1, max_value=24, value=8, step=1)
paid_leave_keyword = st.sidebar.text_input("كلمة الإجازة المدفوعة", value="إجازة مدفوعة")
start_time_info = st.sidebar.selectbox("من الساعة (توجيهي فقط)", options=[f"{h:02d}:00" for h in range(0,24)], index=9)
end_time_info = st.sidebar.selectbox("إلى الساعة (توجيهي فقط)", options=[f"{h:02d}:00" for h in range(0,24)], index=17)

st.markdown(f"**العمل المتعاقد عليه من {start_time_info} إلى {end_time_info} ({contract_hours} ساعة يومياً)**")

# جلب أيام العمل في الشهر
workdays = get_workdays(year, month)
# جلب بيانات الحضور المحفوظة لهذا الموظف والشهر
attendance_df = get_attendance(selected_employee_id, year, month)

# بناء جدول كامل لجميع أيام العمل
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

# عرض الجدول القابل للتعديل (للمدير) أو للقراءة فقط (للموظف)
if user['is_admin']:
    # المدير يمكنه التعديل
    edited_df = st.data_editor(
        df,
        column_config={
            "اليوم": st.column_config.NumberColumn("اليوم", disabled=True),
            "التاريخ": st.column_config.TextColumn("التاريخ", disabled=True),
            "اسم اليوم": st.column_config.TextColumn("اسم اليوم", disabled=True),
            "وقت الحضور": st.column_config.TextColumn("وقت الحضور", help="صيغة HH:MM"),
            "وقت الانصراف": st.column_config.TextColumn("وقت الانصراف", help="صيغة HH:MM"),
            "صافي (ساعات)": st.column_config.NumberColumn("صافي (ساعات)", disabled=True, format="%.2f"),
            "الملاحظات": st.column_config.TextColumn("الملاحظات")
        },
        use_container_width=True,
        num_rows="fixed"
    )
    # تحديث الصافي بناءً على المدخلات
    for idx, row in edited_df.iterrows():
        if row["وقت الحضور"] and row["وقت الانصراف"]:
            net = calculate_net_hours(row["وقت الحضور"], row["وقت الانصراف"])
            edited_df.at[idx, "صافي (ساعات)"] = net
        else:
            edited_df.at[idx, "صافي (ساعات)"] = 0.0
    # حفظ البيانات بعد كل تعديل (نقوم بحذف ثم إدراج جميع أيام الشهر)
    # حذف بيانات الشهر الحالي للموظف
    delete_month_attendance(selected_employee_id, year, month)
    # حفظ الصفوف المعدلة
    for _, row in edited_df.iterrows():
        save_attendance(selected_employee_id, year, month, row["اليوم"],
                        row["وقت الحضور"], row["وقت الانصراف"], row["صافي (ساعات)"], row["الملاحظات"])
    st.success("تم حفظ التغييرات")
else:
    # الموظف يرى فقط (لا يمكنه التعديل)
    st.dataframe(df, use_container_width=True)
    st.info("هذا جدول الحضور الخاص بك. للاستفسار، تواصل مع المدير.")

# حساب الإجماليات
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

# عرض الملخص
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

# جدول ملون (للمدير أو للموظف)
st.subheader("📊 ملخص الجدول (مع تلوين الأيام)")
def color_rows(row):
    notes = str(row["الملاحظات"]) if pd.notna(row["الملاحظات"]) else ""
    if paid_leave_keyword in notes:
        return ["background-color: #fff3cd"] * len(row)
    elif (row["وقت الحضور"] == "" or row["وقت الانصراف"] == "") and row["صافي (ساعات)"] == 0:
        return ["background-color: #f8d7da"] * len(row)
    else:
        return [""] * len(row)

styled_summary = df.style.apply(color_rows, axis=1).format({"صافي (ساعات)": "{:.2f}"})
st.dataframe(styled_summary, use_container_width=True)

# تصدير
st.divider()
if user['is_admin'] or True:  # الكل يمكنه التصدير
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 تحميل كـ CSV", data=csv,
                       file_name=f"attendance_{selected_employee_id}_{year}_{month}.csv", mime="text/csv")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="الحضور")
    st.download_button("📊 تحميل كـ Excel", data=output.getvalue(),
                       file_name=f"attendance_{selected_employee_id}_{year}_{month}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")