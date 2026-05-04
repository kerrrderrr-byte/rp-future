from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import uuid
from datetime import datetime
import json
import os
import requests
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex())

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

# Supabase клиент
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase подключен")
    except Exception as e:
        print(f"⚠️ Supabase error: {e}")

# ============================================
# WORLD SERVICE (Загрузка миров из Supabase или локально)
# ============================================

# Локальная БД миров (используется если Supabase недоступен)
LOCAL_WORLDS = {
    "academy_sakura": {
        "world_name": "Академия Сакура",
        "setting": "Японская старшая школа, весна, цветение сакуры",
        "atmosphere": "Тёплая, уютная, повседневная",
        "main_storyline": "Главный герой переводится в новую школу",
        "genre": "school",
        "description": "Школьная повседневность в японской старшей школе",
        "image_url": "/static/images/worlds/school_preview.png",

                "characters": {
            "narrator": {
                "id": "narrator", "name": "Рассказчик", "role": "narrator",
                "personality": "Нейтральный повествователь",
                "speaking_style": "Литературный, описательный",
                "text_color": "#c0c0c0", "sprite": None
            },
            "garfild": {
                "id": "garfild", "name": "Гарфилд", "role": "староста класса",
                "personality": "Ответственный перфекционист, тайно пишет стихи",
                "speaking_style": "Вежливый, правильная речь",
                "text_color": "#ff8c42", "emoji": "📋",
                "sprite": "boy_garfild", "position": "left"
            },
            "monika": {
                "id": "monika", "name": "Моника", "role": "президент клуба литературы",
                "personality": "Харизматичная, загадочная, скрывает одиночество",
                "speaking_style": "Элегантный, с цитатами",
                "text_color": "#ff69b4", "emoji": "📚",
                "sprite": "girl_monika", "position": "center"
            },
            "reiko": {
                "id": "reiko", "name": "Рейко", "role": "спортсменка",
                "personality": "Энергичная, весёлая, боится потерять стипендию из-за травмы",
                "speaking_style": "Эмоциональный, быстрый",
                "text_color": "#00d4aa", "emoji": "🏃‍♀️",
                "sprite": "girl_reiko", "position": "right"
            },
            "yuki": {
                "id": "yuki", "name": "Юки", "role": "тихая художница",
                "personality": "Застенчивая, говорит через искусство",
                "speaking_style": "Тихий, с паузами",
                "text_color": "#b8a9d4", "emoji": "🎨",
                "sprite": "girl_yuki", "position": "left"
            },
            "takeshi": {
                "id": "takeshi", "name": "Такеши", "role": "хулиган с золотым сердцем",
                "personality": "Грубый снаружи, защищает слабых",
                "speaking_style": "Грубоватый, но искренний",
                "text_color": "#ff4444", "emoji": "👊",
                "sprite": "boy_takeshi", "position": "right"
            },
            "hana": {
                "id": "hana", "name": "Хана", "role": "президент студсовета",
                "personality": "Идеальная, соперничает с Моникой, тайно влюблена в Гарфилда",
                "speaking_style": "Формальный, холодный",
                "text_color": "#4da6ff", "emoji": "👑",
                "sprite": "girl_hana", "position": "center"
            },
            "haru": {
                "id": "haru", "name": "Хару", "role": "лучший друг-весельчак",
                "personality": "Шутник, но очень наблюдательный",
                "speaking_style": "Шутливый, с прибаутками",
                "text_color": "#ffd700", "emoji": "😄",
                "sprite": "boy_haru", "position": "left"
            },
            "akira": {
                "id": "akira", "name": "Акира", "role": "геймер и программист",
                "personality": "Интроверт, создаёт игры",
                "speaking_style": "Технический, с IT-терминами",
                "text_color": "#7cfc00", "emoji": "💻",
                "sprite": "boy_akira", "position": "right"
            },
            "sensei": {
                "id": "sensei", "name": "Танака-сенсей", "role": "классный руководитель",
                "personality": "Мудрый, понимающий, сам пишет роман",
                "speaking_style": "Учительский, с советами",
                "text_color": "#deb887", "emoji": "👨‍🏫",
                "sprite": "boy_sensei", "position": "center"
            },
            "yumi": {
                "id": "yumi", "name": "Юми", "role": "школьная медсестра",
                "personality": "Добрая, заботливая, в прошлом байкер",
                "speaking_style": "Мягкий, успокаивающий",
                "text_color": "#ff9999", "emoji": "💉",
                "sprite": "girl_yumi", "position": "left"
            },
            "ryuu": {
                "id": "ryuu", "name": "Рю", "role": "капитан клуба кендо",
                "personality": "Молчаливый, дисциплинированный",
                "speaking_style": "Краткий, афоризмами",
                "text_color": "#808080", "emoji": "⚔️",
                "sprite": "boy_ryuu", "position": "right"
            },
            "emi": {
                "id": "emi", "name": "Эми", "role": "журналист школьной газеты",
                "personality": "Любопытная, везде ищет сенсации",
                "speaking_style": "Быстрый, с вопросами",
                "text_color": "#ff1493", "emoji": "📰",
                "sprite": "girl_emi", "position": "center"
            }
        },

            "locations": {
        "classroom": {"name": "Класс 2-B", "description": "Светлый класс с большими окнами", "mood": "Спокойный", "bg_image": "bg_classroom"},
        "rooftop": {"name": "Школьная крыша", "description": "Крыша с видом на море и город", "mood": "Романтичный", "bg_image": "bg_rooftop"},
        "library": {"name": "Библиотека", "description": "Трёхэтажная библиотека с пианино", "mood": "Загадочный", "bg_image": "bg_library"},
        "courtyard": {"name": "Школьный двор", "description": "Двор с вековой сакурой", "mood": "Весенний", "bg_image": "bg_courtyard"},
        "cafeteria": {"name": "Столовая", "description": "Просторная столовая с панорамными окнами", "mood": "Шумный", "bg_image": "bg_cafeteria"},
        "gym": {"name": "Спортзал", "description": "Большой спортзал с площадкой", "mood": "Энергичный", "bg_image": "bg_gym"},
        "clubroom": {"name": "Клубная комната", "description": "Уютная комната литклуба", "mood": "Творческий", "bg_image": "bg_clubroom"},
        "nursery": {"name": "Медкабинет", "description": "Светлый кабинет с мятным запахом", "mood": "Успокаивающий", "bg_image": "bg_nursery"},
        "park": {"name": "Приморский парк", "description": "Парк на берегу моря", "mood": "Романтичный", "bg_image": "bg_park"},
        "mall": {"name": "ТЦ Сакура-Молл", "description": "Современный торговый центр", "mood": "Современный", "bg_image": "bg_mall"},
        "beach": {"name": "Пляж", "description": "Песчаный пляж в 15 минутах от школы", "mood": "Свободный", "bg_image": "bg_beach"},
        "shrine": {"name": "Храм", "description": "Старый синтоистский храм на холме", "mood": "Мистический", "bg_image": "bg_shrine"},
        "hallway": {"name": "Коридор", "description": "Школьный коридор со шкафчиками", "mood": "Оживлённый", "bg_image": "bg_hallway"},
        "gate": {"name": "Школьные ворота", "description": "Главные ворота Академии Сакура", "mood": "Встречающий", "bg_image": "bg_gate"},
        "classroom_evening": {"name": "Класс вечером", "description": "Пустой класс после уроков", "mood": "Ностальгический", "bg_image": "bg_classroom_evening"}
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
- Меняй локации по сюжету""",

        "first_scene_prompt": "{player_name} только что перевелся в Академию Сакура. Сегодня его первый день в классе 2-B. Опиши знакомство с одноклассниками."
    }
}


def get_worlds_list():
    """Получить список доступных миров"""
    if supabase and IS_PRODUCTION:
        try:
            result = supabase.table('worlds').select('*').eq('is_active', True).execute()
            if result.data:
                return result.data
        except:
            pass

    # Локальный список
    return [
        {
            'world_id': wid,
            'name': data['world_name'],
            'description': data.get('description', ''),
            'genre': data.get('genre', ''),
            'image_url': data.get('image_url', '')
        }
        for wid, data in LOCAL_WORLDS.items()
    ]


def get_world_data(world_id):
    """Получить полные данные мира"""
    if supabase and IS_PRODUCTION:
        try:
            # Пробуем загрузить из Supabase
            world = supabase.table('worlds').select('*').eq('world_id', world_id).single().execute()
            characters = supabase.table('world_characters').select('*').eq('world_id', world_id).execute()
            locations = supabase.table('world_locations').select('*').eq('world_id', world_id).execute()
            prompts = supabase.table('world_prompts').select('*').eq('world_id', world_id).single().execute()

            if world.data:
                # Собираем персонажей
                chars_dict = {}
                for char in (characters.data or []):
                    chars_dict[char['char_id']] = {
                        'id': char['char_id'],
                        'name': char['name'],
                        'role': char.get('role', ''),
                        'personality': char.get('personality', ''),
                        'speaking_style': char.get('speaking_style', ''),
                        'text_color': char.get('text_color', '#fff'),
                        'emoji': char.get('emoji', ''),
                        'sprite': char.get('sprite_name'),
                        'position': char.get('default_position', 'center')
                    }

                # Собираем локации
                locs_dict = {}
                for loc in (locations.data or []):
                    locs_dict[loc['location_id']] = {
                        'name': loc['name'],
                        'description': loc.get('description', ''),
                        'mood': loc.get('mood', ''),
                        'bg_image': loc.get('bg_image', '')
                    }

                return {
                    'world_name': world.data['name'],
                    'setting': world.data.get('description', ''),
                    'atmosphere': world.data.get('genre', ''),
                    'characters': chars_dict,
                    'locations': locs_dict,
                    'rules_for_ai': prompts.data.get('system_prompt', '') if prompts.data else '',
                    'first_scene_prompt': prompts.data.get('first_scene_prompt', '') if prompts.data else ''
                }
        except Exception as e:
            print(f"⚠️ Ошибка загрузки мира из Supabase: {e}")

    # Возвращаем локальный мир
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
        if result.data:
            game = dict(result.data)
            # Парсим JSON поля обратно
            if isinstance(game.get('game_history'), str):
                game['game_history'] = json.loads(game['game_history'])
            if isinstance(game.get('ai_context'), str):
                game['ai_context'] = json.loads(game['ai_context'])
            return game
        return None
    except Exception as e:
        print(f"❌ Supabase get error: {e}")
        return None


def save_game_supabase(game_data):
    if not supabase: return False
    try:
        # Только нужные колонки для Supabase
        supabase_data = {
            'session_id': game_data['session_id'],
            'player_name': game_data['player_name'],
            'world_id': game_data.get('world_id', 'academy_sakura'),
            'world_name': game_data.get('world_name', 'Академия Сакура'),
            'status': game_data.get('status', 'active'),
            'current_location': game_data.get('current_location', 'classroom'),
            'game_history': json.dumps(game_data.get('game_history', [])),
            'ai_context': json.dumps(game_data.get('ai_context', {}))
        }

        existing = supabase.table('game_sessions').select('id').eq('session_id', game_data['session_id']).execute()
        if existing.data:
            supabase.table('game_sessions').update(supabase_data).eq('session_id', game_data['session_id']).execute()
        else:
            supabase.table('game_sessions').insert(supabase_data).execute()
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
# DEEPSEEK API
# ============================================
def call_deepseek(messages, max_tokens=800):
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
        'temperature': 0.8,
        'stop': None  # Не обрезать ответ
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()

        content = result['choices'][0]['message']['content']

        # Очистка
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()

        # Проверяем что JSON валидный
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Пробуем исправить обрезанный JSON
            # Добавляем недостающие скобки
            if not content.endswith('}'):
                # Находим последнюю валидную строку
                lines = content.split('\n')
                # Убираем последнюю обрезанную строку
                lines = lines[:-1]
                # Добавляем закрывающие скобки
                fixed = '\n'.join(lines) + '\n  }\n}'
                try:
                    return json.loads(fixed)
                except:
                    pass
            raise

    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        print(f"Raw: {content[:300] if 'content' in dir() else 'N/A'}...")
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


@app.route('/api/worlds', methods=['GET'])
def api_get_worlds():
    """Получить список доступных миров"""
    try:
        worlds = get_worlds_list()
        return jsonify({'success': True, 'worlds': worlds})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/create_game', methods=['POST'])
def create_game():
    """Создание новой игры"""
    try:
        data = request.get_json(force=True)
        character_name = data.get('character_name', '').strip()
        world_id = data.get('world_id', 'academy_sakura')

        if not character_name:
            return jsonify({'success': False, 'error': 'Введи имя персонажа!'}), 400

        # Загружаем данные мира
        world_db = get_world_data(world_id)

        session_id = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4]

        # Формируем первый промт
        first_prompt = world_db.get('first_scene_prompt', 'Начинается новая игра.')
        first_prompt = first_prompt.replace('{player_name}', character_name)

        initial_messages = [
            {'role': 'system', 'content': world_db.get('rules_for_ai', '')},
            {'role': 'user', 'content': first_prompt}
        ]

        first_scene = call_deepseek(initial_messages)

        if not first_scene:
            first_scene = get_test_response()

        first_scene['type'] = 'scene'

        # Определяем начальную локацию
        default_location = first_scene.get('location', 'classroom')
        if not default_location or default_location not in world_db.get('locations', {}):
            locations = list(world_db.get('locations', {}).keys())
            default_location = locations[0] if locations else 'classroom'

        game_data = {
            'session_id': session_id,
            'player_name': character_name,
            'world_id': world_id,
            'created_at': datetime.now().isoformat(),
            'status': 'active',
            'current_location': default_location,
            'game_history': [first_scene],
            'ai_context': {
                'world_id': world_id,
                'messages': initial_messages + [
                    {'role': 'assistant', 'content': json.dumps(first_scene, ensure_ascii=False)}
                ]
            }
        }

        save_game(game_data)

        print(f"✅ Игра создана: {character_name} | Мир: {world_id} | ID: {session_id}")

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
    """Обработка действия игрока"""
    try:
        data = request.get_json(force=True)
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
    """Загрузка данных игры"""
    session_id = request.args.get('session', '')
    game = get_game(session_id)

    if not game:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404

    # Загружаем мир
    world_id = game.get('world_id', 'academy_sakura')
    world_db = get_world_data(world_id)

    current_loc = game.get('current_location', 'classroom')
    location_name = world_db.get('locations', {}).get(current_loc, {}).get('name', 'Локация')

    return jsonify({
        'success': True,
        'game': {
            'session_id': game['session_id'],
            'player_name': game['player_name'],
            'world_id': world_id,
            'current_location': current_loc,
            'location_name': location_name,
            'game_history': game.get('game_history', [])
        }
    })


@app.route('/api/health')
def health():
    """Проверка состояния сервера"""
    return jsonify({
        'status': 'ok',
        'mode': 'production' if IS_PRODUCTION else 'local',
        'storage': 'supabase' if (IS_PRODUCTION and supabase) else 'json',
        'api': bool(DEEPSEEK_API_KEY),
        'supabase': bool(supabase),
        'worlds_available': len(get_worlds_list()),
        'timestamp': datetime.now().isoformat()
    })


# ============================================
# ЗАПУСК
# ============================================
if __name__ == '__main__':
    print("=" * 60)
    print("🎮 RP Future - Мульти-мировая новелла")
    print("=" * 60)
    print(f"🔧 Режим: {'PRODUCTION (Render)' if IS_PRODUCTION else 'LOCAL'}")
    print(f"💾 Хранилище: {'Supabase' if (IS_PRODUCTION and supabase) else 'JSON файл'}")
    print(f"🔑 DeepSeek API: {'✅ Подключен' if DEEPSEEK_API_KEY else '⚠️ Тестовый режим'}")
    print(f"🌍 Миров доступно: {len(get_worlds_list())}")
    print("=" * 60)
    print("🌐 http://localhost:5000")
    print("📝 Ctrl+C для остановки")
    print("=" * 60)

    port = int(os.getenv('PORT', 5000))
    debug = not IS_PRODUCTION

    app.run(debug=debug, host='0.0.0.0', port=port, threaded=True)