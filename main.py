from flask import Flask, render_template, request, jsonify, send_from_directory
import uuid
from datetime import datetime
import json
import os
import requests
from dotenv import load_dotenv

# Загружаем .env (локально)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex())

# ============================================
# КОНФИГУРАЦИЯ - АВТОМАТИЧЕСКОЕ ОПРЕДЕЛЕНИЕ РЕЖИМА
# ============================================
IS_PRODUCTION = os.getenv('RENDER', False) or os.getenv('PRODUCTION', False)

# Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# DeepSeek
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'

# Локальное хранилище
STORAGE_FILE = 'games_storage.json'

# Инициализация Supabase (только если есть ключи и не локальный режим)
supabase = None
if SUPABASE_URL and SUPABASE_KEY and IS_PRODUCTION:
    try:
        from supabase import create_client

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase подключен (Production режим)")
    except Exception as e:
        print(f"⚠️ Ошибка Supabase: {e}")

# ============================================
# БАЗА ДАННЫХ МИРА
# ============================================
WORLD_DATABASE = {
    "world_name": "Академия Сакура",
    "setting": "Японская старшая школа в небольшом городе, весна, цветение сакуры",
    "atmosphere": "Тёплая, уютная, повседневная с элементами романтики и дружбы",
    "main_storyline": "Главный герой переводится в новую школу и знакомится с одноклассниками",

    "characters": {
        "narrator": {
            "id": "narrator",
            "name": "Рассказчик",
            "role": "narrator",
            "personality": "Нейтральный повествователь",
            "speaking_style": "Литературный, описательный",
            "text_color": "#c0c0c0",
            "sprite": None
        },
        "garfild": {
            "id": "garfild",
            "name": "Гарфилд",
            "role": "одноклассник, староста класса",
            "personality": "Ответственный, серьёзный, но добрый. Отличник, который всегда готов помочь. Немного занудный.",
            "speaking_style": "Вежливый, правильная речь, иногда вставляет замечания о порядке",
            "text_color": "#ff8c42",
            "emoji": "📋",
            "sprite": "boy_test_garfild",
            "position": "left"
        },
        "monika": {
            "id": "monika",
            "name": "Моника",
            "role": "популярная девушка, президент клуба литературы",
            "personality": "Харизматичная, уверенная, немного загадочная. Любит поэзию и философию.",
            "speaking_style": "Элегантный, с цитатами из книг, иногда задумчивый",
            "text_color": "#ff69b4",
            "emoji": "📚",
            "sprite": "girl_test_monika",
            "position": "center"
        },
        "reiko": {
            "id": "reiko",
            "name": "Рейко",
            "role": "спортсменка, подруга детства",
            "personality": "Энергичная, жизнерадостная, немного неуклюжая. Занимается лёгкой атлетикой.",
            "speaking_style": "Эмоциональный, быстрый, с восклицаниями, использует сленг",
            "text_color": "#00d4aa",
            "emoji": "🏃‍♀️",
            "sprite": "girl_test_reiko",
            "position": "right"
        }
    },

    "locations": {
        "classroom": {
            "name": "Класс 2-B",
            "description": "Светлый класс с большими окнами, вид на школьный двор.",
            "mood": "Спокойный, учебный"
        },
        "rooftop": {
            "name": "Школьная крыша",
            "description": "Открытая крыша с видом на город.",
            "mood": "Романтичный, уединённый"
        },
        "library": {
            "name": "Библиотека",
            "description": "Тихая библиотека с высокими стеллажами.",
            "mood": "Тихий, загадочный"
        },
        "courtyard": {
            "name": "Школьный двор",
            "description": "Двор с цветущими сакурами.",
            "mood": "Оживлённый, весенний"
        }
    },

    "rules_for_ai": """
Ты - рассказчик в визуальной новелле "Академия Сакура". 
Жанр: повседневность, школьная жизнь, романтика.

ГЛАВНЫЕ ПРАВИЛА:
1. Отвечай СТРОГО в формате JSON. Никакого текста вне JSON.
2. Всегда прописывай narrator_text - краткое описание сцены (1 предложение)
3. Если говорит персонаж - пиши его прямую речь в speaker_text
4. Если описываешь сцену - speaker_id = "narrator"
5. ВАЖНО: speaker_text всегда на русском языке
6. В поле "sprites" указывай каких персонажей показывать на сцене и их позиции
7. Персонаж который говорит должен иметь "highlight": true
8. Игрок видит и взаимодействует со всеми персонажами на сцене

ФОРМАТ ОТВЕТА:
{
    "narrator_text": "описание сцены, атмосферы, действий (1-2 предложения)",
    "speaker_id": "garfild/monika/reiko/narrator",
    "speaker_name": "Имя говорящего на русском",
    "speaker_text": "Прямая речь персонажа или описание если narrator",
    "emotion": "радость/грусть/злость/удивление/нейтрально/смущение/восторг",
    "location": "classroom/rooftop/library/courtyard",
    "sprites": {
        "garfild": {"visible": true/false, "position": "left", "highlight": false, "emotion": "normal"},
        "monika": {"visible": true/false, "position": "center", "highlight": false, "emotion": "normal"},
        "reiko": {"visible": true/false, "position": "right", "highlight": false, "emotion": "normal"}
    },
    "choices_available": []
}

ПРАВИЛА СЦЕНЫ:
- На сцене могут быть от 1 до 3 персонажей одновременно
- Только один персонаж говорит за раз
- Говорящий персонаж должен иметь "highlight": true
- Неговорящие персонажи могут реагировать (описывай это в narrator_text)
- Меняй видимость персонажей в зависимости от сцены
"""
}


# ============================================
# ХРАНИЛИЩЕ (Локальное или Supabase)
# ============================================

def load_games_local():
    """Загрузка из локального JSON"""
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
                return {}
        except (json.JSONDecodeError, FileNotFoundError):
            print("⚠️ Файл сохранений повреждён, создаю новый")
            return {}
    return {}


def save_games_local(games):
    """Сохранение в локальный JSON"""
    with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(games, f, ensure_ascii=False, indent=2)


def load_game_supabase(session_id):
    """Загрузка игры из Supabase"""
    if not supabase:
        return None
    try:
        result = supabase.table('game_sessions').select('*').eq('session_id', session_id).single().execute()
        return result.data if result.data else None
    except:
        return None


def save_game_supabase(game_data):
    """Сохранение игры в Supabase"""
    if not supabase:
        return False
    try:
        # Проверяем существует ли запись
        existing = supabase.table('game_sessions').select('id').eq('session_id', game_data['session_id']).execute()

        if existing.data:
            # Обновляем
            supabase.table('game_sessions').update(game_data).eq('session_id', game_data['session_id']).execute()
        else:
            # Создаем
            supabase.table('game_sessions').insert(game_data).execute()
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения в Supabase: {e}")
        return False


def get_game(session_id):
    """Получить игру (локально или из Supabase)"""
    if IS_PRODUCTION and supabase:
        return load_game_supabase(session_id)
    else:
        games = load_games_local()
        return games.get(session_id)


def save_game(game_data):
    """Сохранить игру (локально или в Supabase)"""
    if IS_PRODUCTION and supabase:
        return save_game_supabase(game_data)
    else:
        games = load_games_local()
        games[game_data['session_id']] = game_data
        save_games_local(games)
        return True


# ============================================
# DEEPSEEK API
# ============================================
def call_deepseek(messages, max_tokens=500):
    """Вызов DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        return get_test_response(messages)

    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }

    data = {
        'model': 'deepseek-chat',
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': 0.8,
        'response_format': {'type': 'json_object'}
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return json.loads(result['choices'][0]['message']['content'])
    except Exception as e:
        print(f"❌ Ошибка DeepSeek: {e}")
        return get_test_response(messages)


def get_test_response(messages):
    """Тестовый ответ без API"""
    import random
    responses = [
        {
            "narrator_text": "Солнечный свет заливает класс через большие окна. Весенний ветерок колышет занавески.",
            "speaker_id": "monika",
            "speaker_name": "Моника",
            "speaker_text": "О, привет! Ты, должно быть, новый ученик? Я Моника, президент литературного клуба. Присоединяйся к нам после уроков!",
            "emotion": "радость",
            "location": "classroom",
            "sprites": {
                "garfild": {"visible": True, "position": "left", "highlight": False, "emotion": "normal"},
                "monika": {"visible": True, "position": "center", "highlight": True, "emotion": "happy"},
                "reiko": {"visible": True, "position": "right", "highlight": False, "emotion": "normal"}
            }
        },
        {
            "narrator_text": "Гарфилд поправляет очки и строго смотрит на расписание.",
            "speaker_id": "garfild",
            "speaker_name": "Гарфилд",
            "speaker_text": "Приветствую. Я Гарфилд, староста класса. Если будут вопросы по учёбе - обращайся. Только не опаздывай.",
            "emotion": "нейтрально",
            "location": "classroom",
            "sprites": {
                "garfild": {"visible": True, "position": "left", "highlight": True, "emotion": "serious"},
                "monika": {"visible": True, "position": "center", "highlight": False, "emotion": "normal"},
                "reiko": {"visible": False, "position": "right", "highlight": False, "emotion": "normal"}
            }
        },
        {
            "narrator_text": "Рейко вбегает в класс, чуть не споткнувшись о порог.",
            "speaker_id": "reiko",
            "speaker_name": "Рейко",
            "speaker_text": "ОЙ! Приве-е-ет! Ты новенький? Круто! Я Рейко, давай дружить! У нас тут весело!",
            "emotion": "восторг",
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
# МАРШРУТЫ FLASK
# ============================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/game')
def game_page():
    session_id = request.args.get('session', '')
    game = get_game(session_id)
    if not game:
        return "Игра не найдена. Начните новую игру!", 404
    return render_template('game.html', game=game)


@app.route('/static/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('static/images', filename)


@app.route('/api/create_game', methods=['POST'])
def create_game():
    try:
        data = request.json
        character_name = data.get('character_name', '').strip()
        world_name = data.get('world_name', 'Академия Сакура')

        if not character_name:
            return jsonify({'success': False, 'error': 'Введи имя персонажа!'}), 400

        session_id = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4]

        initial_messages = [
            {
                'role': 'system',
                'content': WORLD_DATABASE['rules_for_ai']
            },
            {
                'role': 'user',
                'content': f'Начинается новая игра. Игрок: {character_name}. Он только что перевёлся в Академию Сакура, класс 2-B. Опиши его первый день в школе. Пусть он встретит кого-то из персонажей.'
            }
        ]

        first_scene = call_deepseek(initial_messages)
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

        print(f"✅ Игра создана: {character_name} | ID: {session_id} | {'Supabase' if IS_PRODUCTION else 'Local'}")

        return jsonify({
            'success': True,
            'session_id': session_id,
            'redirect': f'/game?session={session_id}'
        })

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game_action', methods=['POST'])
def game_action():
    try:
        data = request.json
        session_id = data.get('session_id')
        player_action = data.get('action', '').strip()

        game = get_game(session_id)
        if not game:
            return jsonify({'success': False, 'error': 'Игра не найдена'}), 404

        # Добавляем действие игрока
        game['ai_context']['messages'].append({
            'role': 'user',
            'content': f'Действие игрока: {player_action}'
        })

        game['game_history'].append({
            'type': 'player_action',
            'player_text': player_action
        })

        # Получаем ответ от AI
        scene = call_deepseek(game['ai_context']['messages'])
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
        print(f"❌ Ошибка: {e}")
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
            'location_name': WORLD_DATABASE['locations'][game['current_location']]['name'],
            'game_history': game['game_history']
        }
    })


@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'mode': 'production' if IS_PRODUCTION else 'local',
        'storage': 'supabase' if (IS_PRODUCTION and supabase) else 'json',
        'api_key': bool(DEEPSEEK_API_KEY),
        'timestamp': datetime.now().isoformat()
    })


# ============================================
# ЗАПУСК
# ============================================
if __name__ == '__main__':
    print("=" * 60)
    print("🎮 RP Future - Академия Сакура")
    print("=" * 60)
    print(f"🔧 Режим: {'PRODUCTION (Render)' if IS_PRODUCTION else 'LOCAL'}")
    print(f"💾 Хранилище: {'Supabase' if (IS_PRODUCTION and supabase) else 'JSON файл'}")
    print(f"🔑 DeepSeek API: {'✅ Подключен' if DEEPSEEK_API_KEY else '⚠️ Тестовый режим'}")
    print("=" * 60)
    print("🌐 http://localhost:5000")
    print("📝 Ctrl+C для остановки")
    print("=" * 60)

    port = int(os.getenv('PORT', 5000))
    debug = not IS_PRODUCTION

    app.run(debug=debug, host='0.0.0.0', port=port, threaded=True)