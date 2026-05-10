from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import uuid
from datetime import datetime
import json
import os
import requests
import hashlib
import socket
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex())
socket.setdefaulttimeout(60)

IS_PRODUCTION = os.getenv('RENDER', False) or os.getenv('PRODUCTION', False)
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'

STORAGE_FILE = 'games_storage.json'
USERS_FILE = 'users_storage.json'

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase подключен")
    except Exception as e:
        print(f"⚠️ Supabase error: {e}")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ============================================
# ПОЛЬЗОВАТЕЛИ
# ============================================
def load_users_local():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except:
            pass
    default = {'ADMIN': {'username': 'ADMIN', 'login': 'ADMIN', 'password_hash': hash_password('qwerty123'), 'display_name': 'Администратор', 'is_admin': True}}
    save_users_local(default)
    return default

def save_users_local(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user(login):
    if IS_PRODUCTION and supabase:
        try:
            result = supabase.table('users').select('*').eq('login', login).single().execute()
            return result.data
        except:
            return None
    return load_users_local().get(login)

def create_user(username, login, password, display_name):
    if IS_PRODUCTION and supabase:
        try:
            supabase.table('users').insert({'username': username, 'login': login, 'password_hash': hash_password(password), 'display_name': display_name, 'is_admin': False}).execute()
            return True, 'Пользователь создан'
        except Exception as e:
            return False, str(e)
    else:
        users = load_users_local()
        if login in users: return False, 'Логин занят'
        if any(u['username'] == username for u in users.values()): return False, 'Имя занято'
        users[login] = {'username': username, 'login': login, 'password_hash': hash_password(password), 'display_name': display_name, 'is_admin': False}
        save_users_local(users)
        return True, 'Пользователь создан'

# ============================================
# МИРЫ
# ============================================


def get_worlds_list():
    if supabase and IS_PRODUCTION:
        try:
            result = supabase.table('worlds').select('*').eq('is_active', True).execute()
            if result.data: return result.data
        except: pass
    return [{'world_id': wid, 'name': d['world_name'], 'description': d.get('description',''), 'genre': d.get('genre',''), 'image_url': d.get('image_url','')} for wid, d in LOCAL_WORLDS.items()]

def get_world_data(world_id):
    if supabase and IS_PRODUCTION:
        try:
            world = supabase.table('worlds').select('*').eq('world_id', world_id).single().execute()
            characters = supabase.table('world_characters').select('*').eq('world_id', world_id).execute()
            locations = supabase.table('world_locations').select('*').eq('world_id', world_id).execute()
            prompts = supabase.table('world_prompts').select('*').eq('world_id', world_id).single().execute()
            if world.data:
                chars_dict = {}
                for c in (characters.data or []):
                    chars_dict[c['char_id']] = {'id': c['char_id'], 'name': c['name'], 'role': c.get('role',''), 'personality': c.get('personality',''), 'speaking_style': c.get('speaking_style',''), 'text_color': c.get('text_color','#fff'), 'emoji': c.get('emoji',''), 'sprite': c.get('sprite_name'), 'position': c.get('default_position','center')}
                locs_dict = {}
                for l in (locations.data or []):
                    locs_dict[l['location_id']] = {'name': l['name'], 'description': l.get('description',''), 'mood': l.get('mood',''), 'bg_image': l.get('bg_image','')}
                return {'world_name': world.data['name'], 'setting': world.data.get('description',''), 'atmosphere': world.data.get('genre',''), 'characters': chars_dict, 'locations': locs_dict, 'rules_for_ai': prompts.data.get('system_prompt','') if prompts.data else '', 'first_scene_prompt': prompts.data.get('first_scene_prompt','') if prompts.data else ''}
        except Exception as e:
            print(f"⚠️ Ошибка загрузки мира: {e}")
    return LOCAL_WORLDS.get(world_id, LOCAL_WORLDS['academy_sakura'])

# ============================================
# ХРАНИЛИЩЕ ИГР
# ============================================
def load_games_local():
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except: return {}
    return {}

def save_games_local(games):
    with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(games, f, ensure_ascii=False, indent=2)

def get_game_supabase(session_id):
    if not supabase: return None
    try:
        result = supabase.table('game_sessions').select('*').eq('session_id', session_id).single().execute()
        if result.data:
            game = dict(result.data)
            if isinstance(game.get('game_history'), str): game['game_history'] = json.loads(game['game_history'])
            if isinstance(game.get('ai_context'), str): game['ai_context'] = json.loads(game['ai_context'])
            if isinstance(game.get('relationships'), str): game['relationships'] = json.loads(game['relationships'])
            return game
    except: pass
    return None

def save_game_supabase(game_data):
    if not supabase: return False
    try:
        data = {
            'session_id': game_data['session_id'], 'player_name': game_data['player_name'],
            'world_id': game_data.get('world_id','academy_sakura'), 'world_name': game_data.get('world_name','Академия Сакура'),
            'status': game_data.get('status','active'), 'current_location': game_data.get('current_location','classroom'),
            'game_history': json.dumps(game_data.get('game_history',[]), ensure_ascii=False),
            'ai_context': json.dumps(game_data.get('ai_context',{}), ensure_ascii=False),
            'relationships': json.dumps(game_data.get('relationships',{}), ensure_ascii=False)
        }
        existing = supabase.table('game_sessions').select('id').eq('session_id', game_data['session_id']).execute()
        if existing.data: supabase.table('game_sessions').update(data).eq('session_id', game_data['session_id']).execute()
        else: supabase.table('game_sessions').insert(data).execute()
        return True
    except Exception as e:
        print(f"❌ Supabase save: {e}")
        return False

def get_game(session_id):
    if IS_PRODUCTION and supabase: return get_game_supabase(session_id)
    return load_games_local().get(session_id)

def save_game(game_data):
    if IS_PRODUCTION and supabase: return save_game_supabase(game_data)
    games = load_games_local()
    games[game_data['session_id']] = game_data
    save_games_local(games)
    return True

# ============================================
# DEEPSEEK
# ============================================
def call_deepseek(messages, max_tokens=800):
    if not DEEPSEEK_API_KEY: return get_test_response()
    try:
        resp = requests.post(DEEPSEEK_API_URL, headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'}, json={'model': 'deepseek-chat', 'messages': messages, 'max_tokens': max_tokens, 'temperature': 0.8}, timeout=60)
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content'].strip()
        if content.startswith('```json'): content = content[7:]
        if content.startswith('```'): content = content[3:]
        if content.endswith('```'): content = content[:-3]
        return json.loads(content.strip())
    except Exception as e:
        print(f"❌ DeepSeek: {e}")
        return get_test_response()

def get_test_response():
    import random
    return random.choice([
        {"time_of_day":"morning","response_type":"single_reply","narrator_text":"Солнечный свет заливает класс.","speaker_id":"monika","speaker_name":"Моника","speaker_text":"Привет! Добро пожаловать в Академию Сакура!","emotion":"happy","location":"classroom","dialog_end_marker":"silence","sprites":{"garfild":{"visible":True,"position":"left","highlight":False,"emotion":"normal"},"monika":{"visible":True,"position":"center","highlight":True,"emotion":"happy"},"reiko":{"visible":True,"position":"right","highlight":False,"emotion":"normal"},"yuki":{"visible":False},"takeshi":{"visible":False},"hana":{"visible":False},"haru":{"visible":False},"akira":{"visible":False},"sensei":{"visible":False},"yumi":{"visible":False},"ryuu":{"visible":False},"emi":{"visible":False}}},
        {"time_of_day":"morning","response_type":"single_reply","narrator_text":"Гарфилд поправляет очки.","speaker_id":"garfild","speaker_name":"Гарфилд","speaker_text":"Приветствую. Я староста.","emotion":"serious","location":"classroom","dialog_end_marker":"silence","sprites":{"garfild":{"visible":True,"position":"left","highlight":True,"emotion":"serious"},"monika":{"visible":True,"position":"center","highlight":False,"emotion":"normal"},"reiko":{"visible":False},"yuki":{"visible":False},"takeshi":{"visible":False},"hana":{"visible":False},"haru":{"visible":False},"akira":{"visible":False},"sensei":{"visible":False},"yumi":{"visible":False},"ryuu":{"visible":False},"emi":{"visible":False}}}
    ])

# ============================================
# МАРШРУТЫ
# ============================================
@app.route('/')
def index():
    token = request.cookies.get('auth_token', '')
    if not token: return render_template('login.html')
    user = get_user(token.split(':')[0])
    if not user: return render_template('login.html')
    return render_template('index.html')

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

@app.route('/saves')
def saves_page():
    token = request.cookies.get('auth_token', '')
    if not token: return render_template('login.html')
    user = get_user(token.split(':')[0])
    if not user: return render_template('login.html')
    return render_template('saves.html', user=user)

@app.route('/game')
def game_page():
    session_id = request.args.get('session', '')
    game = get_game(session_id)
    if not game: return "Игра не найдена", 404
    user_agent = request.headers.get('User-Agent', '').lower()
    is_mobile = any(d in user_agent for d in ['mobile', 'android', 'iphone', 'ipad', 'ipod'])
    return render_template('game_mobile.html' if is_mobile else 'game.html', game=game)

@app.route('/static/images/<path:filename>')
def serve_image(filename): return send_from_directory('static/images', filename)

@app.route('/api/worlds')
def api_worlds(): return jsonify({'success': True, 'worlds': get_worlds_list()})

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json(force=True)
    username = data.get('username','').strip(); login = data.get('login','').strip()
    password = data.get('password','').strip(); pc = data.get('password_confirm','').strip()
    dn = data.get('display_name','').strip() or username
    if not all([username, login, password]): return jsonify({'success': False, 'error': 'Все поля обязательны'}), 400
    if len(login) < 3 or len(password) < 4: return jsonify({'success': False, 'error': 'Минимум 3 символа логин, 4 пароль'}), 400
    if password != pc: return jsonify({'success': False, 'error': 'Пароли не совпадают'}), 400
    ok, msg = create_user(username, login, password, dn)
    return jsonify({'success': ok, 'error' if not ok else 'message': msg}), (200 if ok else 400)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True)
    user = get_user(data.get('login','').strip())
    if not user or user['password_hash'] != hash_password(data.get('password','').strip()):
        return jsonify({'success': False, 'error': 'Неверный логин или пароль'}), 401
    token = f"{user['login']}:{hash_password(user['login'] + 'secret')[:16]}"
    resp = jsonify({'success': True, 'user': {'username': user['username'], 'display_name': user.get('display_name', user['username']), 'is_admin': user.get('is_admin', False)}})
    resp.set_cookie('auth_token', token, max_age=30*24*60*60, httponly=True, samesite='Lax')
    return resp

@app.route('/api/logout', methods=['POST'])
def api_logout():
    resp = jsonify({'success': True}); resp.delete_cookie('auth_token'); return resp

@app.route('/api/me')
def api_me():
    token = request.cookies.get('auth_token', '')
    if not token: return jsonify({'success': False}), 401
    user = get_user(token.split(':')[0])
    return jsonify({'success': True, 'user': {'username': user['username'], 'display_name': user.get('display_name', user['username']), 'is_admin': user.get('is_admin', False)}}) if user else jsonify({'success': False}), 401

@app.route('/api/create_game', methods=['POST'])
def create_game():
    data = request.get_json(force=True)
    name = data.get('character_name', '').strip()
    wid = data.get('world_id', 'academy_sakura')
    if not name: return jsonify({'success': False, 'error': 'Введи имя'}), 400
    wdb = LOCAL_WORLDS.get(wid, LOCAL_WORLDS['academy_sakura'])
    sid = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4]
    msgs = [{'role': 'system', 'content': wdb['rules_for_ai']}, {'role': 'user', 'content': wdb.get('first_scene_prompt','').replace('{player_name}', name)}]
    scene = call_deepseek(msgs) or get_test_response()
    scene['type'] = 'scene'
    # Инициализация отношений
    relationships = {}
    for cid in wdb.get('characters', {}):
        if cid != 'narrator': relationships[cid] = 0
    game_data = {'session_id': sid, 'player_name': name, 'world_id': wid, 'created_at': datetime.now().isoformat(), 'status': 'active', 'current_location': scene.get('location','classroom'), 'game_history': [scene], 'relationships': relationships, 'ai_context': {'world_id': wid, 'messages': msgs + [{'role': 'assistant', 'content': json.dumps(scene, ensure_ascii=False)}], 'discovery': {}}}
    save_game(game_data)
    # Синхронизация с профилем
    token = request.cookies.get('auth_token', '')
    if token and supabase and IS_PRODUCTION:
        try:
            supabase.table('player_saves').insert({'user_login': token.split(':')[0], 'session_id': sid, 'player_name': name, 'world_id': wid, 'world_name': wdb.get('world_name',''), 'current_location': scene.get('location','classroom'), 'last_scene_preview': (scene.get('speaker_text','') or scene.get('narrator_text',''))[:100], 'game_history': json.dumps([scene]), 'ai_context': json.dumps(game_data['ai_context']), 'relationships': json.dumps(relationships), 'status': 'active'}).execute()
        except Exception as e: print(f"⚠️ Sync error: {e}")
    return jsonify({'success': True, 'session_id': sid, 'redirect': f'/game?session={sid}'})

@app.route('/api/game_action', methods=['POST'])
def game_action():
    data = request.get_json(force=True)
    game = get_game(data.get('session_id',''))
    if not game: return jsonify({'success': False, 'error': 'Игра не найдена'}), 404
    action = data.get('action','').strip()
    game['ai_context']['messages'].append({'role': 'user', 'content': f'Действие: {action}'})
    game['game_history'].append({'type': 'player_action', 'player_text': action})
    scene = call_deepseek(game['ai_context']['messages']) or get_test_response()
    scene['type'] = 'scene'
    # Обработка отношений
    if 'relationship_changes' in scene and scene['relationship_changes']:
        if 'relationships' not in game: game['relationships'] = {}
        for char_id, change in scene['relationship_changes'].items():
            if char_id == 'narrator': continue
            current = game['relationships'].get(char_id, 0)
            new_value = max(-100, min(100, current + change))
            game['relationships'][char_id] = new_value
    # Автооткрытие персонажей
    if 'sprites' in scene:
        if 'discovery' not in game['ai_context']: game['ai_context']['discovery'] = {}
        for char_id, sprite_data in scene['sprites'].items():
            if char_id == 'narrator': continue
            if sprite_data.get('visible') and not game['ai_context']['discovery'].get(char_id, {}).get('unlocked'):
                game['ai_context']['discovery'][char_id] = {'unlocked': True, 'viewed': False, 'first_met': datetime.now().isoformat()}
                scene['_new_discovery'] = scene.get('_new_discovery', [])
                scene['_new_discovery'].append(char_id)
    game['ai_context']['messages'].append({'role': 'assistant', 'content': json.dumps(scene, ensure_ascii=False)})
    game['game_history'].append(scene)
    if 'location' in scene: game['current_location'] = scene['location']
    save_game(game)
    return jsonify({'success': True, 'scene': scene, 'location': game['current_location']})

@app.route('/api/load_game_data')
def load_game_data():
    game = get_game(request.args.get('session',''))
    if not game: return jsonify({'success': False, 'error': 'Игра не найдена'}), 404
    wdb = LOCAL_WORLDS.get(game.get('world_id','academy_sakura'), LOCAL_WORLDS['academy_sakura'])
    loc_name = wdb.get('locations',{}).get(game.get('current_location','classroom'),{}).get('name','Локация')
    return jsonify({'success': True, 'game': {'session_id': game['session_id'], 'player_name': game['player_name'], 'world_id': game.get('world_id','academy_sakura'), 'current_location': game.get('current_location','classroom'), 'location_name': loc_name, 'game_history': game.get('game_history',[]), 'relationships': game.get('relationships',{})}})

@app.route('/api/saves/list')
def api_saves_list():
    token = request.cookies.get('auth_token','')
    if not token: return jsonify({'success': True, 'saves': []})
    ul = token.split(':')[0]
    saves = []
    if IS_PRODUCTION and supabase:
        try:
            r = supabase.table('player_saves').select('*').eq('user_login', ul).order('last_updated', desc=True).execute()
            saves = r.data or []
        except: pass
    else:
        for sid, g in load_games_local().items():
            saves.append({'session_id': sid, 'player_name': g.get('player_name',''), 'world_id': g.get('world_id',''), 'world_name': g.get('world_name',''), 'current_location': g.get('current_location',''), 'last_updated': g.get('created_at',''), 'created_at': g.get('created_at',''), 'last_scene_preview': g.get('last_scene_preview',''), 'status': g.get('status','active')})
        saves.sort(key=lambda x: x.get('last_updated',''), reverse=True)
    return jsonify({'success': True, 'saves': saves})

@app.route('/api/saves/delete', methods=['POST'])
def api_saves_delete():
    sid = request.get_json(force=True).get('session_id','')
    if IS_PRODUCTION and supabase:
        try:
            supabase.table('player_saves').delete().eq('session_id', sid).execute()
            supabase.table('game_sessions').delete().eq('session_id', sid).execute()
        except: pass
    else:
        g = load_games_local()
        if sid in g: del g[sid]; save_games_local(g)
    return jsonify({'success': True})

@app.route('/api/saves/sync', methods=['POST'])
def api_sync_save():
    token = request.cookies.get('auth_token','')
    data = request.get_json(force=True)
    session_id = data.get('session_id','')
    if not token or not session_id: return jsonify({'success': False}), 400
    game = get_game(session_id)
    if not game: return jsonify({'success': False}), 404
    last_scene = ''
    history = game.get('game_history', [])
    if history:
        last = history[-1]
        last_scene = ('🗣️ ' + last.get('player_text','')) if last.get('type') == 'player_action' else (last.get('speaker_text','') or last.get('narrator_text',''))
    if IS_PRODUCTION and supabase:
        try:
            sd = {'user_login': token.split(':')[0], 'session_id': session_id, 'player_name': game['player_name'], 'world_id': game.get('world_id','academy_sakura'), 'world_name': game.get('world_name',''), 'current_location': game.get('current_location',''), 'last_scene_preview': last_scene[:100], 'game_history': json.dumps(game.get('game_history',[])), 'ai_context': json.dumps(game.get('ai_context',{})), 'relationships': json.dumps(game.get('relationships',{})), 'status': game.get('status','active'), 'last_updated': datetime.now().isoformat()}
            existing = supabase.table('player_saves').select('id').eq('session_id', session_id).execute()
            if existing.data: supabase.table('player_saves').update(sd).eq('session_id', session_id).execute()
            else: supabase.table('player_saves').insert(sd).execute()
        except Exception as e: print(f"❌ Sync error: {e}")
    return jsonify({'success': True})

@app.route('/api/encyclopedia')
def api_encyclopedia():
    session_id = request.args.get('session','')
    game = get_game(session_id)
    wdb = LOCAL_WORLDS['academy_sakura']
    chars = wdb.get('characters', {})
    relationships = game.get('relationships', {}) if game else {}
    discovery = game.get('ai_context', {}).get('discovery', {}) if game else {}
    result = {}
    for cid, c in chars.items():
        if cid == 'narrator': continue
        cd = discovery.get(cid, {})
        result[cid] = {'id': cid, 'name': c.get('name', cid), 'emoji': c.get('emoji',''), 'sprite': c.get('sprite',''), 'text_color': c.get('text_color','#fff'), 'role': c.get('role',''), 'personality': c.get('personality',''), 'unlocked': cd.get('unlocked', False), 'viewed': cd.get('viewed', False), 'relationship': relationships.get(cid, 0)}
    has_new = any(not c.get('viewed') and c.get('unlocked') for c in result.values())
    return jsonify({'success': True, 'characters': result, 'has_new': has_new})

@app.route('/api/encyclopedia/view', methods=['POST'])
def api_encyclopedia_view():
    data = request.get_json(force=True)
    game = get_game(data.get('session_id',''))
    if not game: return jsonify({'success': False}), 404
    char_id = data.get('char_id','')
    if 'discovery' not in game['ai_context']: game['ai_context']['discovery'] = {}
    if char_id in game['ai_context']['discovery']: game['ai_context']['discovery'][char_id]['viewed'] = True
    save_game(game)
    return jsonify({'success': True})

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'mode': 'production' if IS_PRODUCTION else 'local', 'api': bool(DEEPSEEK_API_KEY), 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    print(f"🎮 RP Future | {'PRODUCTION' if IS_PRODUCTION else 'LOCAL'} | API: {'✅' if DEEPSEEK_API_KEY else '⚠️'}")
    app.run(debug=not IS_PRODUCTION, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), threaded=True)