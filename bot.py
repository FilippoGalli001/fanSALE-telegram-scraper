import logging
import asyncio
import httpx 
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
)
from database import (
    setup_database, update_user_data, get_all_users, get_user_trackers, remove_tracker
)
from config import TOKEN, API_KEY, SCRAPER_API_URL

# Configurazione del logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_USERNAME = '@BotUsername'

MAIN_MENU, SEARCH_EVENT, ACTIVE_TRACKERS, REMOVE_TRACKER = range(4)

MAX_TRACKERS = 1

def get_main_menu_keyboard():
    return ReplyKeyboardMarkup([['Cerca evento'], ['Tracker attivi'], ['Info']], resize_keyboard=True)

def get_back_to_menu_button():
    return InlineKeyboardButton("Torna al Menu Principale \U0001F519", callback_data="back_to_menu")

# Handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Benvenuto! Scegli un'opzione:", reply_markup=get_main_menu_keyboard())
    return MAIN_MENU

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text("Benvenuto! Scegli un'opzione:", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU

    text = update.message.text
    if text == 'Cerca evento':
        await update.message.reply_text("Inserisci il nome dell'artista:", reply_markup=ReplyKeyboardRemove())
        return SEARCH_EVENT
    elif text == 'Tracker attivi':
        return await show_active_trackers(update, context)
    elif text == 'Info':
        await update.message.reply_text("Info sul bot: versione 1.0", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU
    else:
        await update.message.reply_text(
            "Opzione non valida. Per favore, scegli un'opzione dal menu.",
            reply_markup=get_main_menu_keyboard()
        )
        return MAIN_MENU

async def handle_selected_artist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chosen_result = context.user_data.get('selected_artist')
    if not chosen_result:
        await update.callback_query.edit_message_text("Errore: nessun artista selezionato.")
        return MAIN_MENU

    link_fanSALE, full_name = chosen_result[2], chosen_result[0]

    # Invia un messaggio di attesa all'utente
    waiting_message = await update.callback_query.message.reply_text("Sto cercando i concerti, questo potrebbe richiedere alcuni secondi...")

    try:
        timeout = httpx.Timeout(15.0, read=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {"x-api-key": API_KEY}
            response = await client.post(
                f"{SCRAPER_API_URL}/write_to_searchbar_and_click_first_result",
                json={"search_text": full_name},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            concert_list = data.get("concert_list", [])

        # Rimuovi il messaggio di attesa
        await waiting_message.delete()

        if not concert_list:
            await update.callback_query.edit_message_text("Non sono stati trovati concerti per l'artista selezionato.")
            return MAIN_MENU

        # Create the keyboard for the concert selection
        keyboard = [
            [InlineKeyboardButton(f"{concert['date']} - {concert['location']}", callback_data=f"concert_{concert['date']}")]
            for concert in concert_list
        ]
        keyboard.append([get_back_to_menu_button()])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.edit_message_text("Seleziona un concerto disponibile:", reply_markup=reply_markup)

    except httpx.HTTPStatusError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        await waiting_message.delete()
        await update.callback_query.edit_message_text("Si è verificato un errore durante la ricerca dei concerti. Riprova")
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Errore durante la gestione dell'artista selezionato: {e}")
        await waiting_message.delete()
        await update.callback_query.edit_message_text("Si è verificato un errore durante la ricerca dei concerti. Riprova")
        return MAIN_MENU

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_menu":
        await query.message.reply_text("Ritorno al menu principale...", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU

    elif query.data.startswith('name_'):
        selected_artist_name = query.data.split('_', 1)[1]
        results_list = context.user_data.get('results_list', [])
        selected_artist_info = next((res for res in results_list if res[0] == selected_artist_name), None)

        if selected_artist_info:
            context.user_data['selected_artist'] = selected_artist_info
            context.user_data['artist_name'] = selected_artist_name  # Salva il nome dell'artista

            # Mostra il messaggio di attesa e poi chiama la funzione per gestire l'artista selezionato
            return await handle_selected_artist(update, context)
        else:
            await query.edit_message_text("Errore: artista selezionato non trovato.")

    elif query.data.startswith('concert_'):
        selected_concert_date = query.data[len('concert_'):]
        context.user_data['selected_date'] = selected_concert_date
        chosen_result = context.user_data['selected_artist']
        link_fanSALE = chosen_result[2]
        artist_name = context.user_data.get('artist_name', 'Artista Sconosciuto')

        user_id = update.effective_user.id

        # Verifica il numero di tracker attivi per l'utente
        trackers = get_user_trackers(user_id)
        if len(trackers) >= MAX_TRACKERS:
            await query.edit_message_text(
                f"Hai già {MAX_TRACKERS} tracker {'attivo' if MAX_TRACKERS == 1 else 'attivi'}. Per favore, rimuovi {'il tracker' if MAX_TRACKERS == 1 else 'un tracker'} prima di aggiungerne uno nuovo."
            )
            await asyncio.sleep(2)
            await query.message.reply_text("Torno al menu principale.", reply_markup=get_main_menu_keyboard())
            return MAIN_MENU

        # Aggiungi il nuovo tracker
        update_user_data(user_id, artist_name, link_fanSALE, selected_concert_date)

        await query.edit_message_text(
            "La tua ricerca è stata salvata. Ti avviseremo quando ci saranno nuovi biglietti disponibili."
        )
        await asyncio.sleep(2)
        await query.message.reply_text("Torno al menu principale.", reply_markup=get_main_menu_keyboard())

    return MAIN_MENU

async def search_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        return SEARCH_EVENT

    artist_name = update.message.text

    # Invia un messaggio di attesa all'utente
    waiting_message = await update.message.reply_text("Sto cercando gli eventi, l'operazione potrebbe richiedere alcuni secondi...")

    try:
        timeout = httpx.Timeout(15.0, read=30.0)  # Timeout di 10 secondi per la connessione, 20 secondi per la lettura
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {"x-api-key": API_KEY}
            response = await client.post(
                f"{SCRAPER_API_URL}/search_artist",
                json={"artist_name": artist_name},
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            results_list = data.get("results_list", [])
            context.user_data['results_list'] = results_list

        # Rimuovi il messaggio di attesa
        await waiting_message.delete()

        if not results_list:
            await update.message.reply_text(f"Nessun evento trovato per '{artist_name}'.")
            return await start(update, context)

        keyboard = [
            [InlineKeyboardButton(result_name[:59], callback_data=f'name_{result_name[:59]}')]
            for result_name, _, _ in results_list
        ]
        keyboard.append([get_back_to_menu_button()])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Seleziona un evento per '{artist_name}':", reply_markup=reply_markup)

        return MAIN_MENU

    except httpx.HTTPStatusError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        await waiting_message.delete()
        await update.message.reply_text("Si è verificato un errore durante la ricerca dell'artista. Riprova")
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Errore durante la ricerca dell'artista: {e}")
        await waiting_message.delete()
        await update.message.reply_text("Si è verificato un errore durante la ricerca dell'artista. Riprova")
        return MAIN_MENU

async def show_active_trackers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    trackers = get_user_trackers(user_id)

    if not trackers:
        await update.message.reply_text("Non hai tracker attivi.", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU

    keyboard = [['Torna al menu principale \U0001F519']] + [
        [f"Rimuovi: {artist_name} - Concerto del {concert_date}"]
        for artist_name, _, concert_date in trackers
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "I tuoi tracker attivi. Seleziona un tracker per rimuoverlo:",
        reply_markup=reply_markup
    )
    return REMOVE_TRACKER

async def remove_tracker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == 'Torna al menu principale \U0001F519':
        return await start(update, context)

    if text.startswith("Rimuovi: "):
        try:
            _, rest = text.split("Rimuovi: ", 1)
            artist_part, date_part = rest.split(" - Concerto del ")
            artist_name = artist_part.strip()
            concert_date = date_part.strip()
            user_id = update.effective_user.id
            trackers = get_user_trackers(user_id)

            for db_artist_name, link_fansale, db_concert_date in trackers:
                if db_artist_name == artist_name and db_concert_date == concert_date:
                    remove_tracker(user_id, link_fansale, concert_date)
                    await update.message.reply_text(f"Tracker per {artist_name} - concerto del {concert_date} rimosso.")
                    return await show_active_trackers(update, context)

            await update.message.reply_text("Tracker non trovato. Riprova.")
            return REMOVE_TRACKER
        except Exception as e:
            logger.error(f"Errore durante la rimozione del tracker: {e}")
            await update.message.reply_text("Formato non valido. Riprova.")
            return REMOVE_TRACKER

    await update.message.reply_text(
        "Opzione non valida. Seleziona un tracker da rimuovere o torna al menu principale."
    )
    return REMOVE_TRACKER

# Job per controllare i biglietti
async def check_tickets(context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    timeout = httpx.Timeout(15.0, read=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        headers = {"x-api-key": API_KEY}
        for user_id, artist_name, link_fanSALE, selected_concert_date in users:
            try:
                # Chiamata al microservizio per cercare i biglietti
                response = await client.post(
                    f"{SCRAPER_API_URL}/search_tickets",
                    json={"url": link_fanSALE},
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                tickets = data.get("ticket_data", [])

                if not isinstance(tickets, list):
                    logger.warning(f"Formato dei biglietti inatteso per l'utente {user_id}: {tickets}")
                    continue

                # Chiamata al microservizio per fare il match
                match_response = await client.post(
                    f"{SCRAPER_API_URL}/match_tickets",
                    json={"tickets": tickets, "user_ticket": selected_concert_date},
                    headers=headers
                )
                match_response.raise_for_status()
                match_data = match_response.json()
                matched_tickets = match_data.get("matched_tickets", [])

                if matched_tickets:
                    message = f"Nuovi biglietti disponibili per {artist_name} - concerto del {selected_concert_date}:\n"

                    for ticket in matched_tickets:
                        message += f"Luogo: {ticket.get('location', 'N/A')}, Prezzo: {ticket.get('price', 'N/A')}\n"

                    await context.bot.send_message(chat_id=user_id, text=message)
            except httpx.HTTPStatusError as http_err:
                logger.error(f"HTTP error per l'utente {user_id}: {http_err}")
            except Exception as e:
                logger.error(f"Errore durante il processamento dei biglietti per l'utente {user_id}: {str(e)}")

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

def main():
    logger.info('Starting bot...')
    setup_database()
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu),
                CallbackQueryHandler(main_menu, pattern="^back_to_menu$")
            ],
            SEARCH_EVENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_event)],
            ACTIVE_TRACKERS: [CallbackQueryHandler(remove_tracker_handler, pattern='^remove_')],
            REMOVE_TRACKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_tracker_handler)],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    # Job queue per controllare i biglietti ogni 30 minuti
    job_queue = app.job_queue
    job_queue.run_repeating(check_tickets, interval=1800, first=15)

    logger.info("Polling...")
    app.run_polling()

if __name__ == '__main__':
    main()
