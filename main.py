from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import uuid
from datetime import datetime
import json
import os
import requests
from dotenv import load_dotenv

# Загружаем .env (локально)
load_dotenv()

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для мобильных запросов
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex())

# Увеличиваем таймаут для мобильных запросов
import socket

socket.setdefaulttimeout(60)

# ============================================
# КОНФИГУРАЦИЯ
# ============================================
IS_PRODUCTION = os.getenv('RENDER', False) or os.getenv('PRODUCTION', False)

SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'

STORAGE_FILE = 'games_storage.json'

# Supabase
supabase = None
if SUPABASE_URL and SUPABASE_KEY and IS_PRODUCTION:
    try:
        from supabase import create_client

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase подключен (Production)")
    except Exception as e:
        print(f"⚠️ Supabase error: {e}")

# ============================================
# БАЗА ДАННЫХ МИРА
# ============================================
WORLD_DATABASE = {
    "world_name": "Академия Сакура",
    "setting": "Японская старшая школа, весна, цветение сакуры",
    "atmosphere": "Тёплая, уютная, повседневная",
    "main_storyline": "Главный герой переводится в новую школу",

    "characters": {
        "narrator": {
            "id": "narrator", "name": "Рассказчик", "role": "narrator",
            "personality": "Нейтральный повествователь",
            "speaking_style": "Литературный, описательный",
            "text_color": "#c0c0c0", "sprite": None
        },
        "garfild": {
            "id": "garfild", "name": "Гарфилд", "role": "староста класса",
            "personality": "Ответственный, добрый, немного занудный",
            "speaking_style": "Вежливый, правильная речь",
            "text_color": "#ff8c42", "emoji": "📋",
            "sprite": "boy_test_garfild", "position": "left"
        },
        "monika": {
            "id": "monika", "name": "Моника", "role": "президент клуба литературы",
            "personality": "Харизматичная, загадочная, любит поэзию",
            "speaking_style": "Элегантный, с цитатами",
            "text_color": "#ff69b4", "emoji": "📚",
            "sprite": "girl_test_monika", "position": "center"
        },
        "reiko": {
            "id": "reiko", "name": "Рейко", "role": "спортсменка",
            "personality": "Энергичная, весёлая, прямолинейная",
            "speaking_style": "Эмоциональный, быстрый",
            "text_color": "#00d4aa", "emoji": "🏃‍♀️",
            "sprite": "girl_test_reiko", "position": "right"
        }
    },

    "locations": {
        "classroom": {"name": "Класс 2-B", "description": "Светлый класс с большими окнами", "mood": "Спокойный"},
        "rooftop": {"name": "Школьная крыша", "description": "Крыша с видом на город", "mood": "Романтичный"},
        "library": {"name": "Библиотека", "description": "Тихая библиотека", "mood": "Загадочный"},
        "courtyard": {"name": "Школьный двор", "description": "Двор с сакурами", "mood": "Весенний"}
    },

    "rules_for_ai": """Ты - рассказчик в визуальной новелле "Академия Сакура". Жанр: повседневность, школа, романтика.

ОТВЕЧАЙ СТРОГО ТОЛЬКО JSON, БЕЗ ЛЮБОГО ТЕКСТА ДО И ПОСЛЕ.

ФОРМАТ:
{
    "narrator_text": "описание сцены",
    "speaker_id": "garfild/monika/reiko/narrator",
    "speaker_name": "имя",
    "speaker_text": "речь персонажа",
    "emotion": "normal/happy/sad/angry/surprised/excited/serious",
    "location": "classroom/rooftop/library/courtyard",
    "sprites": {
        "garfild": {"visible": true/false, "position": "left", "highlight": true/false, "emotion": "normal"},
        "monika": {"visible": true/false, "position": "center", "highlight": true/false, "emotion": "normal"},
        "reiko": {"visible": true/false, "position": "right", "highlight": true/false, "emotion": "normal"}
    }
}

ПРАВИЛА:
- Всегда narrator_text (1 предложение)
- speaker_text на русском
- Говорящий персонаж: highlight=true
- Можно показывать 1-3 персонажа
- Меняй локации по сюжету"""
}


# ============================================
# ХРАНИЛИЩЕ
# ============================================
def load_games_local():
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except:
            return {}
    return {}


def save_games_local(games):
    with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(games, f, ensure_ascii=False, indent=2)


def get_game_supabase(session_id):
    if not supabase: return None
    try:
        result = supabase.table('game_sessions').select('*').eq('session_id', session_id).single().execute()
        return result.data if result.data else None
    except:
        return None


def save_game_supabase(game_data):
    if not supabase: return False
    try:
        existing = supabase.table('game_sessions').select('id').eq('session_id', game_data['session_id']).execute()
        if existing.data:
            supabase.table('game_sessions').update(game_data).eq('session_id', game_data['session_id']).execute()
        else:
            supabase.table('game_sessions').insert(game_data).execute()
        return True
    except Exception as e:
        print(f"❌ Supabase save error: {e}")
        return False


def get_game(session_id):
    if IS_PRODUCTION and supabase:
        return get_game_supabase(session_id)
    games = load_games_local()
    return games.get(session_id)


def save_game(game_data):
    if IS_PRODUCTION and supabase:
        return save_game_supabase(game_data)
    games = load_games_local()
    games[game_data['session_id']] = game_data
    save_games_local(games)
    return True


# ============================================
# DEEPSEEK API (с фиксом для мобильных)
# ============================================
def call_deepseek(messages, max_tokens=500):
    if not DEEPSEEK_API_KEY:
        return get_test_response()

    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }

    data = {
        'model': 'deepseek-chat',
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': 0.8
    }

    try:
        # Увеличенный таймаут для мобильных
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=data,
            timeout=45  # Увеличено для мобильных сетей
        )
        response.raise_for_status()
        result = response.json()

        # Пробуем распарсить JSON из ответа
        content = result['choices'][0]['message']['content']

        # Очищаем от возможных марккодовых блоков
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()

        return json.loads(content)

    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        print(f"Raw content: {content[:200]}...")
        return get_test_response()
    except requests.Timeout:
        print("❌ DeepSeek Timeout")
        return get_test_response()
    except Exception as e:
        print(f"❌ DeepSeek Error: {e}")
        return get_test_response()


def get_test_response():
    import random
    responses = [
        {
            "narrator_text": "Солнечный свет заливает класс через большие окна.",
            "speaker_id": "monika",
            "speaker_name": "Моника",
            "speaker_text": "О, привет! Ты новый ученик? Я Моника. Добро пожаловать в Академию Сакура!",
            "emotion": "happy",
            "location": "classroom",
            "sprites": {
                "garfild": {"visible": True, "position": "left", "highlight": False, "emotion": "normal"},
                "monika": {"visible": True, "position": "center", "highlight": True, "emotion": "happy"},
                "reiko": {"visible": True, "position": "right", "highlight": False, "emotion": "normal"}
            }
        },
        {
            "narrator_text": "Гарфилд поправляет очки и смотрит на расписание.",
            "speaker_id": "garfild",
            "speaker_name": "Гарфилд",
            "speaker_text": "Приветствую. Я староста класса. Обращайся если нужна помощь с учёбой.",
            "emotion": "serious",
            "location": "classroom",
            "sprites": {
                "garfild": {"visible": True, "position": "left", "highlight": True, "emotion": "serious"},
                "monika": {"visible": True, "position": "center", "highlight": False, "emotion": "normal"},
                "reiko": {"visible": False, "position": "right", "highlight": False, "emotion": "normal"}
            }
        },
        {
            "narrator_text": "Рейко вбегает в класс, чуть не споткнувшись.",
            "speaker_id": "reiko",
            "speaker_name": "Рейко",
            "speaker_text": "ОЙ! Приве-е-ет! Ты новенький? Давай дружить! У нас тут весело!",
            "emotion": "excited",
            "location": "classroom",
            "sprites": {
                "garfild": {"visible": False, "position": "left", "highlight": False, "emotion": "normal"},
                "monika": {"visible": False, "position": "center", "highlight": False, "emotion": "normal"},
                "reiko": {"visible": True, "position": "center", "highlight": True, "emotion": "excited"}
            }
        }
    ]
    return random.choice(responses)


# ============================================
# МАРШРУТЫ
# ============================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/game')
def game_page():
    session_id = request.args.get('session', '')
    game = get_game(session_id)
    if not game:
        return "Игра не найдена", 404
    return render_template('game.html', game=game)


@app.route('/static/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('static/images', filename)


@app.route('/api/create_game', methods=['POST'])
def create_game():
    try:
        data = request.get_json(force=True)  # force=True для мобильных
        character_name = data.get('character_name', '').strip()
        world_name = data.get('world_name', 'Академия Сакура')

        if not character_name:
            return jsonify({'success': False, 'error': 'Введи имя!'}), 400

        session_id = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4]

        # Первое сообщение
        initial_messages = [
            {'role': 'system', 'content': WORLD_DATABASE['rules_for_ai']},
            {'role': 'user',
             'content': f'Новая игра. Игрок: {character_name}. Первый день в Академии Сакура, класс 2-B.'}
        ]

        first_scene = call_deepseek(initial_messages)

        if not first_scene:
            first_scene = get_test_response()

        first_scene['type'] = 'scene'

        game_data = {
            'session_id': session_id,
            'player_name': character_name,
            'world_name': world_name,
            'created_at': datetime.now().isoformat(),
            'status': 'active',
            'current_location': first_scene.get('location', 'classroom'),
            'game_history': [first_scene],
            'ai_context': {
                'messages': initial_messages + [
                    {'role': 'assistant', 'content': json.dumps(first_scene, ensure_ascii=False)}
                ]
            }
        }

        save_game(game_data)
        print(f"✅ Игра: {character_name} | {session_id} | {'Supabase' if IS_PRODUCTION else 'Local'}")

        return jsonify({
            'success': True,
            'session_id': session_id,
            'redirect': f'/game?session={session_id}'
        })

    except Exception as e:
        print(f"❌ Create error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game_action', methods=['POST'])
def game_action():
    try:
        data = request.get_json(force=True)
        session_id = data.get('session_id')
        player_action = data.get('action', '').strip()

        game = get_game(session_id)
        if not game:
            return jsonify({'success': False, 'error': 'Игра не найдена'}), 404

        # Добавляем действие
        game['ai_context']['messages'].append({
            'role': 'user',
            'content': f'Действие: {player_action}'
        })

        game['game_history'].append({
            'type': 'player_action',
            'player_text': player_action
        })

        # Ответ от AI
        scene = call_deepseek(game['ai_context']['messages'])

        if not scene:
            scene = get_test_response()

        scene['type'] = 'scene'

        game['ai_context']['messages'].append({
            'role': 'assistant',
            'content': json.dumps(scene, ensure_ascii=False)
        })
        game['game_history'].append(scene)

        if 'location' in scene:
            game['current_location'] = scene['location']

        save_game(game)

        return jsonify({
            'success': True,
            'scene': scene,
            'location': game['current_location']
        })

    except Exception as e:
        print(f"❌ Action error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/load_game_data')
def load_game_data():
    session_id = request.args.get('session', '')
    game = get_game(session_id)

    if not game:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404

    return jsonify({
        'success': True,
        'game': {
            'session_id': game['session_id'],
            'player_name': game['player_name'],
            'world_name': game['world_name'],
            'current_location': game['current_location'],
            'location_name': WORLD_DATABASE['locations'].get(game['current_location'], {}).get('name', 'Класс'),
            'game_history': game['game_history']
        }
    })


@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'mode': 'production' if IS_PRODUCTION else 'local',
        'storage': 'supabase' if (IS_PRODUCTION and supabase) else 'json',
        'api': bool(DEEPSEEK_API_KEY),
        'timestamp': datetime.now().isoformat()
    })


# ============================================
# ЗАПУСК
# ============================================
if __name__ == '__main__':
    print("=" * 50)
    print("🎮 RP Future - Академия Сакура")
    print("=" * 50)
    print(f"🔧 Режим: {'PRODUCTION' if IS_PRODUCTION else 'LOCAL'}")
    print(f"💾 Хранение: {'Supabase' if (IS_PRODUCTION and supabase) else 'JSON'}")
    print(f"🔑 API: {'✅' if DEEPSEEK_API_KEY else '⚠️ Тест'}")
    print("=" * 50)

    port = int(os.getenv('PORT', 5000))
    debug = not IS_PRODUCTION

    app.run(debug=debug, host='0.0.0.0', port=port, threaded=True)