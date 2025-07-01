import os
import uuid
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiohttp import web
import asyncio

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
ADMIN_GROUP_ID = os.getenv('ADMIN_GROUP_ID')

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Стейты для FSM
class OrderStates(StatesGroup):
    GET_TARGET_USERNAME = State()
    GET_QUANTITY = State()
    GET_PAYMENT_METHOD = State()
    TOTAL_VALUE = State()
    CONFIRMATION = State()

# Временное хранилище заказов
orders = {}

# Курс покупки звезд
rate = 1.7

# Комиссия
commission = 1

# Способы оплаты
PAYMENT_METHODS = [
    "💳 Банковская карта",
    "📱 ЮMoney",
    "🪙 Криптовалюта (USDT)",
    "✏️ Другой способ"
]

# Популярные количества
QUANTITY_OPTIONS = [50, 100, 250, 500, 1000]

@dp.message(Command('start'))
async def start_cmd(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="🛒 Сделать заказ"))
    builder.add(types.KeyboardButton(text="📝 Посмотреть отзывы"))
    await message.answer(
        "🌟 <b>Добро пожаловать в магазин звёзд!</b>",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="HTML"
    )

@dp.message(F.text == "📝 Посмотреть отзывы")
async def show_reviews(message: types.Message):
    await message.answer("🔍 Наши отзывы: https://t.me/fasters_tg_feedback")

@dp.message(F.text == "🛒 Сделать заказ")
async def start_order(message: types.Message, state: FSMContext):
    await state.set_state(OrderStates.GET_TARGET_USERNAME)
    
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="🔹 Покупаю себе"))
    builder.adjust(1)
    
    await message.answer(
        "✏️ <b>Введите username получателя</b> (начинается с @)\n"
        "Или нажмите кнопку ниже если покупаете себе:",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="HTML"
    )

@dp.message(OrderStates.GET_TARGET_USERNAME)
async def get_username(message: types.Message, state: FSMContext):
    if message.text == "🔹 Покупаю себе":
        username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
        await state.update_data(target_username=username)
    elif not message.text.startswith("@"):
        await message.answer("❌ Username должен начинаться с @!")
        return
    else:
        await state.update_data(target_username=message.text)
    
    await state.set_state(OrderStates.GET_QUANTITY)
    
    # Создаем кнопки с популярными количествами
    builder = ReplyKeyboardBuilder()
    for qty in QUANTITY_OPTIONS:
        builder.add(types.KeyboardButton(text=str(qty)))
    builder.adjust(3)
    
    await message.answer(
        "🔢 <b>Выберите количество или введите своё</b> (от 50):",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="HTML"
    )

@dp.message(OrderStates.GET_QUANTITY)
async def get_quantity(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 50:
        await message.answer("❌ Введите число от 50!")
        return
        
    await state.update_data(quantity=message.text)
    await state.set_state(OrderStates.GET_PAYMENT_METHOD)

    await state.update_data(total_value=int(message.text) * rate * commission)
    
    # Создаем кнопки с способами оплаты
    builder = ReplyKeyboardBuilder()
    for method in PAYMENT_METHODS:
        builder.add(types.KeyboardButton(text=method))
    builder.adjust(2)
    
    await message.answer(
        "💳 <b>Выберите способ оплаты:</b>",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="HTML"
    )

@dp.message(OrderStates.GET_PAYMENT_METHOD)
async def get_payment_method(message: types.Message, state: FSMContext):
    payment_method = message.text
    user_data = await state.get_data()

    # Если выбран "Другой способ", просим уточнить
    if payment_method == "✏️ Другой способ":
        await message.answer(
            "✏️ <b>Укажите ваш способ оплаты:</b>",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        return

    # Расчёт суммы
    quantity = int(user_data["quantity"])
    total_value = quantity * rate * commission

    order_id = str(uuid.uuid4())
    
    order_data = {
        "order_id": order_id,
        "user_id": message.from_user.id,
        "target_username": user_data['target_username'],
        "quantity": quantity,
        "payment_method": payment_method,
        "total_value": round(total_value, 2)  # округлим до копеек
    }

    orders[order_id] = order_data
    await state.update_data(order_id=order_id)
    
    # Удаляем кнопки оплаты перед подтверждением
    await message.answer(
        "✅ <b>Проверьте ваш заказ:</b>",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    
    summary = (
    "📋 <b>Детали заказа:</b>\n\n"
    f"🎯 <b>Получатель:</b> {user_data['target_username']}\n"
    f"🔢 <b>Количество:</b> {user_data['quantity']}\n"
    f"💳 <b>Способ оплаты:</b> {payment_method}\n"
    f"💸 <b>К оплате:</b> {order_data['total_value']:.2f} ₽\n"
    "<i>Подтвердите или отмените заказ</i>"
)
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="✅ Подтвердить",
        callback_data=f"confirm_{order_id}"))
    builder.add(types.InlineKeyboardButton(
        text="❌ Отменить",
        callback_data=f"cancel_{order_id}"))
    builder.adjust(2)
    
    await state.set_state(OrderStates.CONFIRMATION)
    await message.answer(
        summary,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("confirm_"), OrderStates.CONFIRMATION)
async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.split("_")[1]
    order_data = orders.get(order_id)
    
    # Показываем кнопки заново
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="🛒 Сделать заказ"))
    builder.add(types.KeyboardButton(text="📝 Посмотреть отзывы"))

    if not order_data:
        await callback.message.answer("⚠️ Заказ не найден!")
        return
    
    # Формируем сообщение для админа
    admin_msg = (
        "🆕 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
        f"🆔 <b>ID заказа:</b> <code>{order_data['order_id']}</code>\n"
        f"👤 <b>Клиент:</b> @{callback.from_user.username or 'без юзернейма'}\n"
        f"🆔 <b>User ID:</b> <code>{order_data['user_id']}</code>\n"
        f"🎯 <b>Получатель:</b> {order_data['target_username']}\n"
        f"🔢 <b>Количество:</b> {order_data['quantity']}\n"
        f"💸 <b>К оплате:</b> {order_data['total_value']:.2f} ₽\n"
        f"💳 <b>Оплата:</b> {order_data['payment_method']}"
    )
    
    # Кнопки для админа
    admin_builder = InlineKeyboardBuilder()
    admin_builder.add(types.InlineKeyboardButton(
        text="✅ Подтвердить",
        callback_data=f"admin_approve_{order_id}"))
    admin_builder.add(types.InlineKeyboardButton(
        text="❌ Отклонить",
        callback_data=f"admin_reject_{order_id}"))
    admin_builder.add(types.InlineKeyboardButton(
        text="📨 Написать клиенту",
        url=f"tg://user?id={order_data['user_id']}"))
    admin_builder.adjust(2, 1)
    
    # Отправляем заказ админу
    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=admin_msg,
        reply_markup=admin_builder.as_markup(),
        parse_mode="HTML"
    )
    
    # Сообщение пользователю
    await callback.message.answer(
       f"💸 <b>Заказ создан</b>",
       parse_mode="HTML",
       reply_markup=builder.as_markup(resize_keyboard=True)
    )

    # 📩 Инструкция по оплате с кликабельным ID и ссылкой
    await callback.message.answer(
        f"💸 <b>Для завершения покупки</b> перешлите ID вашего заказа:\n"
        f"<code>{order_id}</code>\n"
        f"👉 <a href='https://t.me/fasters_admin'>Сюда</a> (нажмите, чтобы перейти)",
        parse_mode="HTML"
    )

    await state.clear()
    del orders[order_id]

@dp.callback_query(F.data.startswith("cancel_"), OrderStates.CONFIRMATION)
async def cancel_order(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.split("_")[1]

    # Возвращаем главное меню
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="🛒 Сделать заказ"))
    builder.add(types.KeyboardButton(text="📝 Посмотреть отзывы"))

    await callback.message.answer(
        f"❌ <b>Заказ отменен</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    
    await state.clear()
    if order_id in orders:
        del orders[order_id]

@dp.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_order(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[2]
    
    # Пересылаем заказ в группу
    approved_msg = (
        "✅ <b>ЗАКАЗ ПОДТВЕРЖДЕН</b>\n\n" +
        callback.message.text.split("\n\n", 1)[1]  # Берем текст без первого заголовка
    )
    
    await bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=approved_msg,
        parse_mode="HTML"
    )
    
    # Удаляем сообщение с кнопками
    await callback.message.delete()
    
    # Уведомляем админа
    await callback.answer("Заказ подтверждён и отправлен в группу!")

@dp.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_order(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[2]
    
    # Удаляем сообщение с заказом
    await callback.message.delete()
    
    # Уведомляем админа
    await callback.answer("Заказ отклонён и удалён", show_alert=True)

# Веб сервер
async def handle_ping(request):
    print("/ping recieved")
    return web.Response(text="OK")

# Веб сервер
async def start_web():
    app = web.Application()
    app.router.add_get('/ping', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080)))
    await site.start()

async def main():
    # Запускаем веб-сервер
    await start_web()
    # Запускаем polling бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())