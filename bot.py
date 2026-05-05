import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
import requests
import json
import threading
import time

# ==========================================
# CONFIGURAÇÕES OBRIGATÓRIAS
# ==========================================
TOKEN = '7999657881:AAGpM6T3gqdlXYhdCDeW-zmTOFA8kUYY7rw'
SUPABASE_URL = 'https://chdcyhxyoatmiktpczov.supabase.co'
SUPABASE_ANON_KEY = 'sb_publishable_yFdGGlEJbsVC48gH-QWaTQ_u9SnC719'

# SOMENTE ESTE ID (DONO) PODE USAR
OWNER_ID = 8565342363

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# ==========================================
# FUNÇÕES DE BANCO DE DADOS (SUPABASE)
# ==========================================
def db_request(method, endpoint, data=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    try:
        if method == 'GET':
            res = requests.get(url, headers=headers)
        elif method == 'POST':
            res = requests.post(url, headers=headers, json=data)
        elif method == 'PATCH':
            res = requests.patch(url, headers=headers, json=data)
        elif method == 'DELETE':
            res = requests.delete(url, headers=headers)
        
        res.raise_for_status()
        return res.json() if res.text else []
    except Exception as e:
        print(f"[Supabase DB Error] {method} {endpoint}: {e}")
        return []

def is_owner(user_id):
    return user_id == OWNER_ID

# ==========================================
# EVENTO: BOT FOI ADICIONADO NUM GRUPO
# ==========================================
@bot.my_chat_member_handler()
def on_bot_status_changed(message: ChatMemberUpdated):
    chat = message.chat
    new_status = message.new_chat_member.status
    
    if chat.type in ['group', 'supergroup']:
        if new_status in ['member', 'administrator']: # Bot entrou
            group_data = {
                "chat_id": chat.id, 
                "title": chat.title,
                "interval_minutes": 60,
                "is_running": False,
                "last_product_id": 0,
                "next_run_at": 0
            }
            existing = db_request('GET', f'user_groups?chat_id=eq.{chat.id}')
            if not existing:
                db_request('POST', 'user_groups', group_data)
            else:
                db_request('PATCH', f'user_groups?chat_id=eq.{chat.id}', {"title": chat.title})
                
            bot.send_message(OWNER_ID, f"✅ O bot foi inserido no grupo: <b>{chat.title}</b>")
            
        elif new_status in ['kicked', 'left']: # Bot foi removido
            db_request('DELETE', f'user_groups?chat_id=eq.{chat.id}')
            bot.send_message(OWNER_ID, f"❌ O bot foi removido do grupo: <b>{chat.title}</b>")

# ==========================================
# MENUS DE OPÇÕES (Privado)
# ==========================================
def send_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📋 Meus Grupos", callback_data="menu_grupos"),
        InlineKeyboardButton("📦 Minha Fila Ativa", callback_data="menu_produtos"),
        InlineKeyboardButton("➕ Adicionar Produto", callback_data="menu_add_produto"),
        InlineKeyboardButton("❌ Remover Produto", callback_data="menu_rem_produto"),
        InlineKeyboardButton("⏱ Configurar Cronômetro", callback_data="menu_cronometro")
    )
    bot.send_message(chat_id, "🏠 <b>Painel de Controle</b>\nEscolha uma opção:", reply_markup=markup)

@bot.message_handler(commands=['start', 'menu'])
def start_cmd(message):
    if not is_owner(message.from_user.id): return

    # Sincronizador de grupo manual (Caso a detecção automática falhe)
    if message.chat.type in ['group', 'supergroup']:
        chat = message.chat
        group_data = {
            "chat_id": chat.id, 
            "title": chat.title,
            "interval_minutes": 60,
            "is_running": False,
            "last_product_id": 0,
            "next_run_at": 0
        }
        existing = db_request('GET', f'user_groups?chat_id=eq.{chat.id}')
        if not existing:
            db_request('POST', 'user_groups', group_data)
        else:
            db_request('PATCH', f'user_groups?chat_id=eq.{chat.id}', {"title": chat.title})
        
        bot.delete_message(message.chat.id, message.message_id) # apaga o start do grupo
        bot.send_message(OWNER_ID, f"✅ O grupo <b>{chat.title}</b> foi sincronizado com sucesso!")
        return
    
    send_main_menu(message.chat.id)

# ==========================================
# CLIQUES NOS BOTÕES INLINE
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if not is_owner(call.from_user.id): return
    
    cid = call.message.chat.id
    mid = call.message.message_id
    
    if call.data == "menu_grupos":
        grupos = db_request('GET', 'user_groups')
        if not grupos:
            bot.edit_message_text("Nenhum grupo ativo. Adicione em um grupo e mande /start lá.", cid, mid)
            send_main_menu(cid)
        else:
            msg = "📋 <b>Lista de Grupos:</b>\n\n"
            for g in grupos:
                status = "🟢 LIGADO" if g.get('is_running') else "🔴 DESLIGADO"
                msg += f"🔹 {g['title']} | {status}\n"
            bot.edit_message_text(msg, cid, mid, parse_mode='HTML')
            send_main_menu(cid)

    elif call.data == "menu_produtos":
        produtos = db_request('GET', 'products?order=id.asc')
        if not produtos:
            bot.edit_message_text("Não há nada na fila de postagens no momento.", cid, mid)
            send_main_menu(cid)
        else:
            msg = "📦 <b>Fila de Postagens:</b>\n"
            for p in produtos:
                desc = p.get('description', 'Sem info.')
                msg += f"\n🔸 <b>ID {p['id']}</b> - {desc}"
            bot.edit_message_text(msg, cid, mid, parse_mode='HTML')
            send_main_menu(cid)

    elif call.data == "menu_add_produto":
        bot.delete_message(cid, mid)
        msg = bot.send_message(
            cid, 
            "📝 Mande a mensagem EXATAMENTE como você quer que eu publique.\n"
            "(Pode ser uma Foto com Legenda, um texto simples, um vídeo, etc)"
        )
        bot.register_next_step_handler(msg, process_add_product)

    elif call.data == "menu_rem_produto":
        produtos = db_request('GET', 'products?order=id.asc')
        if not produtos:
            bot.edit_message_text("Sua fila já está vazia.", cid, mid)
            send_main_menu(cid)
            return

        msg = "⭕️ <b>Remover Postagem:</b>\n\n"
        for p in produtos:
            msg += f"ID: <code>{p['id']}</code> - {p.get('description', '')}\n"
        
        bot.delete_message(cid, mid)
        sent = bot.send_message(cid, msg + "\nDigite APENAS o número ID para excluir:")
        bot.register_next_step_handler(sent, process_del_produto)

    elif call.data == "menu_cronometro":
        grupos = db_request('GET', 'user_groups')
        if not grupos:
            bot.edit_message_text("Sem grupos registrados.", cid, mid)
            send_main_menu(cid)
            return
            
        markup = InlineKeyboardMarkup()
        for g in grupos:
            markup.add(InlineKeyboardButton(f"{g['title']}", callback_data=f"cfg_{g['chat_id']}"))
            
        bot.edit_message_text("⏱ Selecione o grupo que quer configurar:", cid, mid, reply_markup=markup)

    elif call.data.startswith("cfg_"):
        chat_id = call.data.replace("cfg_", "")
        grupo = db_request('GET', f'user_groups?chat_id=eq.{chat_id}')
        if not grupo: return
        
        g = grupo[0]
        markup = InlineKeyboardMarkup()
        
        status_txt = "✅ Ligado" if g.get('is_running') else "❌ Desligado"
        toggle = f"toggle_off_{chat_id}" if g.get('is_running') else f"toggle_on_{chat_id}"
        
        markup.add(InlineKeyboardButton(f"{status_txt} (clique para mudar)", callback_data=toggle))
        markup.add(InlineKeyboardButton("⏳ Ajustar Tempo (Minutos)", callback_data=f"time_{chat_id}"))
        markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="menu_cronometro"))
        
        bot.edit_message_text(
            f"<b>Grupo:{g['title']}</b>\nIntervalo: A cada {g.get('interval_minutes')} min.\n",
            cid, mid, reply_markup=markup, parse_mode='HTML'
        )

    elif call.data.startswith("toggle_on_") or call.data.startswith("toggle_off_"):
        chat_id = call.data.split('_')[2]
        new_status = call.data.startswith("toggle_on_")
        
        up_data = {"is_running": new_status}
        if new_status: 
            up_data["next_run_at"] = int(time.time())
            
        db_request('PATCH', f'user_groups?chat_id=eq.{chat_id}', up_data)
        bot.answer_callback_query(call.id, "Modificado com Sucesso!")
        call.data = f"cfg_{chat_id}"
        callback_handler(call)

    elif call.data.startswith("time_"):
        chat_id = call.data.split('_')[1]
        bot.delete_message(cid, mid)
        msg = bot.send_message(cid, "⏱ De quantos em quantos minutos esse grupo divulgará?")
        bot.register_next_step_handler(msg, process_change_time, chat_id)

    elif call.data == "prod_done":
        bot.edit_message_text("✅ Feito! Entrou na fila.", cid, mid)
        send_main_menu(cid)
        
    elif call.data.startswith("prod_btn_"):
        prod_id = call.data.replace("prod_btn_", "")
        bot.delete_message(cid, mid)
        msg = bot.send_message(
            cid, 
            "Envie os links (você pode mandar vários) separados por linha, dessa forma:\n\n"
            "<code>Comprar - https://shopee.com...</code>\n"
            "<code>Falar no Zap - https://wa.me/....</code>"
        )
        bot.register_next_step_handler(msg, process_add_buttons, prod_id)

# ==========================================
# PASSOS (STEPS DE CONVERSA)
# ==========================================
def process_add_product(message):
    try:
        msg_id = message.message_id
        
        desc = "Sem texto" # Breve descrição pra vc saber qual é
        if message.text: desc = message.text[:20].replace('\n', ' ') + "..."
        elif message.caption: desc = message.caption[:20].replace('\n', ' ') + "..."
        
        data = {
            "message_id": msg_id,
            "description": desc,
            "buttons": []
        }
        res = db_request('POST', 'products', data)
        
        if not res:
            bot.send_message(message.chat.id, "Problema ao salvar no banco (Verifique a API SUPABASE).")
            send_main_menu(message.chat.id)
            return
            
        prod_id = res[0]['id']
        
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("➕ Adicionar Botões Embaixo (Opcional)", callback_data=f"prod_btn_{prod_id}"),
            InlineKeyboardButton("✅ Concluir (Não quero Botão)", callback_data="prod_done")
        )
        bot.send_message(message.chat.id, "✅ Conteúdo arquivado na fila! Quer colocar botões nela?", reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, "Ocorreu um erro.")

def process_add_buttons(message, prod_id):
    botoes = []
    # Lê as linhas e guarda os links
    for l in message.text.split('\n'):
        if ' - ' in l:
            try:
                nome, url = l.split(' - ', 1)
                botoes.append({"title": nome.strip(), "url": url.strip()})
            except: pass

    if botoes:
        db_request('PATCH', f'products?id=eq.{prod_id}', {"buttons": botoes})
        bot.send_message(message.chat.id, "✅ Botões linkados na postagem!")
    else:
        bot.send_message(message.chat.id, "Falha: Você não seguiu o Formato Nome - Link.")
    send_main_menu(message.chat.id)

def process_del_produto(message):
    try:
        pid = int(message.text.strip())
        db_request('DELETE', f"products?id=eq.{pid}")
        bot.send_message(message.chat.id, f"✅ O ID {pid} foi removido da fila!")
    except:
        bot.send_message(message.chat.id, "❌ ID inválido inserido.")
    send_main_menu(message.chat.id)

def process_change_time(message, chat_id):
    try:
        minutos = int(message.text.strip())
        db_request('PATCH', f'user_groups?chat_id=eq.{chat_id}', {"interval_minutes": minutos})
        bot.send_message(message.chat.id, f"✅ Tempo atualizado para {minutos} min.")
    except:
        bot.send_message(message.chat.id, "Apenas números inteiros, tente novamente depois.")
    send_main_menu(message.chat.id)

# ==========================================
# LOOP INFINITO (O CRONÔMETRO DE DISPARO) 
# ==========================================
def broadcast_worker():
    while True:
        try:
            timestamp_agora = int(time.time())
            # Procura qual grupo tá na hora de disparar algo
            grupos_on = db_request('GET', f"user_groups?is_running=eq.true&next_run_at=lte.{timestamp_agora}")
            
            if grupos_on:
                for g in grupos_on:
                    chat_id = g['chat_id']
                    last_id = g.get('last_product_id', 0)
                    
                    # Pega o próximo item depois do que foi disparado por último
                    produtos = db_request('GET', f'products?id=gt.{last_id}&order=id.asc&limit=1')
                    
                    # Se não retornar é pq a fila acabou. Recomeça do 1°
                    if not produtos:
                        produtos = db_request('GET', 'products?order=id.asc&limit=1')
                        
                    if produtos:
                        prod = produtos[0]
                        orig_msg_id = prod['message_id']
                        
                        # Processa botões guardados se existirem
                        botoes = prod.get('buttons', [])
                        if isinstance(botoes, str):
                            try: botoes = json.loads(botoes)
                            except: botoes = []

                        reply_markup = None
                        if botoes:
                            markup = InlineKeyboardMarkup()
                            for b in botoes:
                                markup.add(InlineKeyboardButton(b['title'], url=b['url']))
                            reply_markup = markup

                        success = False
                        try:
                            # A mágica do CLONE do telegram. Isso copia sua mensagem como se fosse própria para lá:
                            if reply_markup is not None:
                                bot.copy_message(chat_id=chat_id, from_chat_id=OWNER_ID, message_id=orig_msg_id, reply_markup=reply_markup)
                            else:
                                bot.copy_message(chat_id=chat_id, from_chat_id=OWNER_ID, message_id=orig_msg_id)
                            success = True
                        except Exception as e:
                            # Trata remoções
                            if "kicked" in str(e).lower() or "not found" in str(e).lower():
                                db_request('DELETE', f"user_groups?chat_id=eq.{chat_id}")
                                continue
                            elif "to copy not found" in str(e).lower():
                                success = True # Pula pois o post no chat Privado foi deletado por você

                        if success:
                            # Adiciona X minutos em Segundos no tempo e salva o próximo disparo
                            proximo_disparo = int(time.time()) + (g['interval_minutes'] * 60)
                            db_request('PATCH', f'user_groups?chat_id=eq.{chat_id}', {
                                "last_product_id": prod['id'],
                                "next_run_at": proximo_disparo
                            })

        except Exception as e:
            time.sleep(5)
            
        time.sleep(10) # Repete a verificação a cada 10 segundos

# ==========================================
# INICIAR BOTS
# ==========================================
if __name__ == "__main__":
    t = threading.Thread(target=broadcast_worker)
    t.daemon = True
    t.start()
    
    bot.delete_webhook(drop_pending_updates=True)
    bot.infinity_polling()