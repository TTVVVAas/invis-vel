"""
Utilitários para gerenciamento de gravações por data
"""

import os
from datetime import datetime
import logging
from config import RECORDING

logger = logging.getLogger(__name__)

def get_month_name(month_num):
    """Retorna o nome do mês em português"""
    months = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    return months.get(month_num, 'Desconhecido')

def get_recordings_base_path():
    """Retorna o caminho base para gravações"""
    base_path = RECORDING.get('storage_path', 'recordings')
    return base_path.rstrip('/\\')

def get_recording_path_for_date(date=None):
    """
    Retorna o caminho completo para gravações de uma data específica
    Estrutura: recordings/ano/mes_nome/dia/
    """
    if date is None:
        date = datetime.now()
    
    year = str(date.year)
    month_name = f"{date.month:02d}_{get_month_name(date.month)}"
    day = f"{date.day:02d}"
    
    base_path = get_recordings_base_path()
    full_path = os.path.join(base_path, year, month_name, day)
    
    return full_path

def ensure_recording_directory_exists(date=None):
    """
    Garante que o diretório de gravações para a data existe
    Cria a estrutura de pastas se necessário
    """
    path = get_recording_path_for_date(date)
    
    try:
        os.makedirs(path, exist_ok=True)
        logger.info(f"Diretório de gravações garantido: {path}")
        return path
    except Exception as e:
        logger.error(f"Erro ao criar diretório de gravações: {e}")
        return None

def generate_recording_filename(date=None):
    """
    Gera um nome de arquivo único para gravação
    Formato: clip_HH:MMhDD/MM/YY.mp4
    """
    if date is None:
        date = datetime.now()
    
    time_str = date.strftime("%H:%M")
    date_str = date.strftime("%d/%m/%y")
    
    filename = f"clip_{time_str}h{date_str}.mp4"
    
    # Substituir caracteres problemáticos para sistemas de arquivo
    filename = filename.replace('/', '-').replace(':', '-')
    
    return filename

def get_all_recordings():
    """
    Retorna todas as gravações organizadas por data
    Estrutura: {ano: {mes: {dia: [arquivos]}}}
    """
    base_path = get_recordings_base_path()
    recordings = {}
    
    if not os.path.exists(base_path):
        return recordings
    
    try:
        # Percorrer anos
        for year in sorted(os.listdir(base_path)):
            year_path = os.path.join(base_path, year)
            if not os.path.isdir(year_path):
                continue
            
            recordings[year] = {}
            
            # Percorrer meses
            for month in sorted(os.listdir(year_path)):
                month_path = os.path.join(year_path, month)
                if not os.path.isdir(month_path):
                    continue
                
                recordings[year][month] = {}
                
                # Percorrer dias
                for day in sorted(os.listdir(month_path)):
                    day_path = os.path.join(month_path, day)
                    if not os.path.isdir(day_path):
                        continue
                    
                    # Listar arquivos de vídeo
                    video_files = []
                    for file in sorted(os.listdir(day_path)):
                        if file.endswith('.mp4'):
                            file_path = os.path.join(day_path, file)
                            try:
                                stat = os.stat(file_path)
                                video_files.append({
                                    'filename': file,
                                    'path': file_path,
                                    'size': stat.st_size,
                                    'size_formatted': f"{stat.st_size / (1024*1024):.1f} MB",
                                    'created': datetime.fromtimestamp(stat.st_ctime).strftime("%d/%m/%Y %H:%M:%S"),
                                    'url': f"/recordings/{year}/{month}/{day}/{file}"
                                })
                            except Exception as e:
                                logger.error(f"Erro ao obter info do arquivo {file}: {e}")
                    
                    recordings[year][month][day] = video_files
    
    except Exception as e:
        logger.error(f"Erro ao listar gravações: {e}")
    
    return recordings

def get_recordings_by_year_month(year, month):
    """
    Retorna gravações de um ano e mês específicos
    """
    all_recordings = get_all_recordings()
    return all_recordings.get(year, {}).get(month, {})

def get_recordings_by_date(year, month, day):
    """
    Retorna gravações de uma data específica
    """
    all_recordings = get_all_recordings()
    return all_recordings.get(year, {}).get(month, {}).get(day, [])

def format_file_size(size_bytes):
    """Formata tamanho de arquivo em bytes para formato legível"""
    if size_bytes == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    
    return f"{size_bytes:.1f} TB"

def parse_recording_filename(filename):
    """
    Tenta extrair informações do nome do arquivo de gravação
    Formato esperado: clip_HH-MMhDD-MM-YY.mp4
    """
    try:
        # Remover extensão
        name_without_ext = filename.replace('.mp4', '')
        
        # Separar partes
        parts = name_without_ext.split('h')
        if len(parts) != 2:
            return None
        
        time_part = parts[0].replace('clip_', '')
        date_part = parts[1]
        
        # Substituir traços de volta para barras e dois pontos
        time_str = time_part.replace('-', ':')
        date_str = date_part.replace('-', '/')
        
        return {
            'time': time_str,
            'date': date_str,
            'datetime_str': f"{date_str} {time_str}"
        }
    except:
        return None
