# world_service.py
import json
from supabase import create_client
import os

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')


class WorldService:
    def __init__(self):
        self.supabase = None
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            except:
                pass

    def get_worlds(self):
        """Получить список доступных миров"""
        if not self.supabase:
            return self._get_default_worlds()

        try:
            result = self.supabase.table('worlds').select('*').eq('is_active', True).execute()
            return result.data if result.data else self._get_default_worlds()
        except:
            return self._get_default_worlds()

    def get_world_data(self, world_id):
        """Получить полные данные мира"""
        if not self.supabase:
            return self._get_default_world_data(world_id)

        try:
            # Получаем мир
            world = self.supabase.table('worlds').select('*').eq('world_id', world_id).single().execute()

            # Персонажи
            characters = self.supabase.table('world_characters').select('*').eq('world_id', world_id).execute()

            # Локации
            locations = self.supabase.table('world_locations').select('*').eq('world_id', world_id).execute()

            # Промты
            prompts = self.supabase.table('world_prompts').select('*').eq('world_id', world_id).single().execute()

            return {
                'world': world.data,
                'characters': characters.data,
                'locations': locations.data,
                'prompts': prompts.data
            }
        except:
            return self._get_default_world_data(world_id)

    def build_world_database(self, world_id):
        """Собрать базу данных мира для AI"""
        data = self.get_world_data(world_id)

        characters_dict = {}
        locations_dict = {}

        for char in data.get('characters', []):
            characters_dict[char['char_id']] = {
                'id': char['char_id'],
                'name': char['name'],
                'role': char['role'],
                'personality': char['personality'],
                'speaking_style': char['speaking_style'],
                'text_color': char['text_color'],
                'emoji': char['emoji'],
                'sprite': char.get('sprite_name'),
                'position': char.get('default_position')
            }

        for loc in data.get('locations', []):
            locations_dict[loc['location_id']] = {
                'name': loc['name'],
                'description': loc['description'],
                'mood': loc['mood'],
                'bg_image': loc.get('bg_image')
            }

        return {
            'world_name': data.get('world', {}).get('name', ''),
            'setting': data.get('world', {}).get('description', ''),
            'atmosphere': data.get('world', {}).get('genre', ''),
            'characters': characters_dict,
            'locations': locations_dict,
            'rules_for_ai': data.get('prompts', {}).get('system_prompt', ''),
            'first_scene_prompt': data.get('prompts', {}).get('first_scene_prompt', ''),
            'response_format': data.get('prompts', {}).get('response_format', '{}')
        }

    def _get_default_worlds(self):
        """Миры по умолчанию (если Supabase недоступен)"""
        return [
            {
                'world_id': 'academy_sakura',
                'name': 'Академия Сакура',
                'description': 'Школьная повседневность в японской старшей школе',
                'genre': 'school',
                'image_url': '/static/images/worlds/school_preview.png'
            }
        ]

    def _get_default_world_data(self, world_id):
        """Данные мира по умолчанию"""
        from main import WORLD_DATABASE  # Импортируем существующую БД

        return {
            'world': {
                'world_id': 'academy_sakura',
                'name': 'Академия Сакура',
                'description': 'Японская старшая школа',
                'genre': 'school'
            },
            'characters': [
                {'char_id': cid, **data} for cid, data in WORLD_DATABASE['characters'].items()
            ],
            'locations': [
                {'location_id': lid, **data} for lid, data in WORLD_DATABASE['locations'].items()
            ],
            'prompts': {
                'system_prompt': WORLD_DATABASE['rules_for_ai'],
                'first_scene_prompt': 'Первый день в школе',
                'response_format': '{}'
            }
        }