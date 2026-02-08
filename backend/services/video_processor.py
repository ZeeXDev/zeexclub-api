# backend/services/video_processor.py
"""
Processeur vidéo pour ZeeXClub
Extraction de métadonnées, thumbnails, et optimisation
"""

import logging
import tempfile
import os
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False
    logger.warning("⚠️ ffmpeg-python non installé - traitement vidéo limité")


@dataclass
class VideoMetadata:
    """Métadonnées extraites d'une vidéo"""
    duration: Optional[int] = None  # secondes
    width: Optional[int] = None
    height: Optional[int] = None
    bitrate: Optional[int] = None
    fps: Optional[float] = None
    codec: Optional[str] = None
    audio_codec: Optional[str] = None
    file_size: Optional[int] = None
    format_name: Optional[str] = None
    
    @property
    def resolution(self) -> Optional[str]:
        """Retourne la résolution formatée"""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return None
    
    @property
    def is_hd(self) -> bool:
        """Vérifie si la vidéo est HD"""
        return (self.height or 0) >= 720
    
    @property
    def is_full_hd(self) -> bool:
        """Vérifie si la vidéo est Full HD"""
        return (self.height or 0) >= 1080
    
    @property
    def is_4k(self) -> bool:
        """Vérifie si la vidéo est 4K"""
        return (self.height or 0) >= 2160


class VideoProcessor:
    """
    Processeur vidéo avec extraction de métadonnées
    et génération de thumbnails
    """
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.ffmpeg_available = self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> bool:
        """Vérifie si ffmpeg est disponible sur le système"""
        if not FFMPEG_AVAILABLE:
            return False
        
        try:
            import subprocess
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            logger.warning("⚠️ FFmpeg non trouvé sur le système")
            return False
    
    def extract_metadata(self, file_path: str) -> VideoMetadata:
        """
        Extrait les métadonnées d'un fichier vidéo
        
        Args:
            file_path: Chemin vers le fichier vidéo
        
        Returns:
            VideoMetadata: Métadonnées extraites
        """
        metadata = VideoMetadata()
        
        # Taille du fichier
        try:
            metadata.file_size = os.path.getsize(file_path)
        except OSError:
            pass
        
        if not self.ffmpeg_available:
            logger.warning("FFmpeg non disponible, métadonnées limitées")
            return metadata
        
        try:
            # Utiliser ffmpeg-python pour probe
            probe = ffmpeg.probe(file_path)
            
            # Informations format
            format_info = probe.get('format', {})
            metadata.duration = int(float(format_info.get('duration', 0)))
            metadata.bitrate = int(format_info.get('bit_rate', 0))
            metadata.format_name = format_info.get('format_name', '').split(',')[0]
            
            # Trouver le flux vidéo
            video_stream = None
            for stream in probe.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if video_stream:
                metadata.width = int(video_stream.get('width', 0)) or None
                metadata.height = int(video_stream.get('height', 0)) or None
                metadata.codec = video_stream.get('codec_name')
                
                # FPS
                fps_str = video_stream.get('r_frame_rate', '0/1')
                try:
                    num, den = map(int, fps_str.split('/'))
                    metadata.fps = round(num / den, 2) if den != 0 else None
                except ValueError:
                    pass
            
            # Trouver le flux audio
            audio_stream = None
            for stream in probe.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    audio_stream = stream
                    break
            
            if audio_stream:
                metadata.audio_codec = audio_stream.get('codec_name')
            
            logger.info(f"✅ Métadonnées extraites: {metadata.resolution}, {metadata.duration}s")
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction métadonnées: {e}")
        
        return metadata
    
    def generate_thumbnail(
        self,
        file_path: str,
        time_position: Optional[float] = None,
        width: int = 640,
        height: int = 360
    ) -> Optional[str]:
        """
        Génère une thumbnail à partir de la vidéo
        
        Args:
            file_path: Chemin vers la vidéo
            time_position: Position en secondes (défaut: 10% de la durée)
            width: Largeur de la thumbnail
            height: Hauteur de la thumbnail
        
        Returns:
            str: Chemin vers la thumbnail générée ou None
        """
        if not self.ffmpeg_available:
            logger.warning("FFmpeg non disponible, thumbnail non générée")
            return None
        
        try:
            # Déterminer la position temporelle
            if time_position is None:
                metadata = self.extract_metadata(file_path)
                time_position = (metadata.duration or 0) * 0.1  # 10%
            
            # Nom de fichier de sortie
            base_name = Path(file_path).stem
            output_path = os.path.join(
                self.temp_dir,
                f"{base_name}_thumb_{int(time_position)}.jpg"
            )
            
            # Générer avec ffmpeg
            (
                ffmpeg
                .input(file_path, ss=time_position)
                .filter('scale', width, height, force_original_aspect_ratio='decrease')
                .filter('pad', width, height, '(ow-iw)/2', '(oh-ih)/2')
                .output(output_path, vframes=1, q=2)
                .overwrite_output()
                .run(quiet=True)
            )
            
            if os.path.exists(output_path):
                logger.info(f"✅ Thumbnail générée: {output_path}")
                return output_path
            
        except Exception as e:
            logger.error(f"❌ Erreur génération thumbnail: {e}")
        
        return None
    
    def generate_multiple_thumbnails(
        self,
        file_path: str,
        count: int = 4
    ) -> list:
        """
        Génère plusieurs thumbnails à différents moments
        
        Args:
            file_path: Chemin vers la vidéo
            count: Nombre de thumbnails à générer
        
        Returns:
            list: Liste des chemins des thumbnails
        """
        metadata = self.extract_metadata(file_path)
        duration = metadata.duration or 0
        
        if duration == 0:
            return []
        
        thumbnails = []
        interval = duration / (count + 1)
        
        for i in range(1, count + 1):
            position = interval * i
            thumb_path = self.generate_thumbnail(file_path, position)
            if thumb_path:
                thumbnails.append({
                    'path': thumb_path,
                    'position': position,
                    'position_percent': (position / duration) * 100
                })
        
        return thumbnails
    
    def convert_to_streaming_format(
        self,
        input_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Convertit une vidéo en format optimal pour le streaming
        
        Args:
            input_path: Chemin d'entrée
            output_path: Chemin de sortie (optionnel)
        
        Returns:
            str: Chemin du fichier converti ou None
        """
        if not self.ffmpeg_available:
            return None
        
        if output_path is None:
            base = Path(input_path).stem
            output_path = os.path.join(self.temp_dir, f"{base}_stream.mp4")
        
        try:
            # Configuration pour streaming web
            (
                ffmpeg
                .input(input_path)
                .output(
                    output_path,
                    vcodec='libx264',
                    acodec='aac',
                    preset='fast',
                    movflags='+faststart',  # Optimisé pour streaming
                    video_bitrate='2M',
                    audio_bitrate='128k',
                    threads=4
                )
                .overwrite_output()
                .run(quiet=True)
            )
            
            logger.info(f"✅ Vidéo convertie pour streaming: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Erreur conversion: {e}")
            return None
    
    def extract_audio(
        self,
        video_path: str,
        output_format: str = 'mp3'
    ) -> Optional[str]:
        """
        Extrait la piste audio d'une vidéo
        
        Args:
            video_path: Chemin de la vidéo
            output_format: Format de sortie (mp3, aac, etc.)
        
        Returns:
            str: Chemin du fichier audio ou None
        """
        if not self.ffmpeg_available:
            return None
        
        try:
            base = Path(video_path).stem
            output_path = os.path.join(self.temp_dir, f"{base}_audio.{output_format}")
            
            (
                ffmpeg
                .input(video_path)
                .output(output_path, vn=None, acodec='libmp3lame' if output_format == 'mp3' else 'aac')
                .overwrite_output()
                .run(quiet=True)
            )
            
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction audio: {e}")
            return None
    
    def create_preview_gif(
        self,
        file_path: str,
        duration: float = 3.0,
        fps: int = 10,
        width: int = 480
    ) -> Optional[str]:
        """
        Crée un GIF de preview animé
        
        Args:
            file_path: Chemin de la vidéo
            duration: Durée du GIF en secondes
            fps: Images par seconde
            width: Largeur du GIF
        
        Returns:
            str: Chemin du GIF ou None
        """
        if not self.ffmpeg_available:
            return None
        
        try:
            metadata = self.extract_metadata(file_path)
            video_duration = metadata.duration or 0
            
            # Position au milieu de la vidéo
            start_time = max(0, (video_duration - duration) / 2)
            
            base = Path(file_path).stem
            output_path = os.path.join(self.temp_dir, f"{base}_preview.gif")
            
            # Palette optimisée pour GIF
            palette_path = os.path.join(self.temp_dir, "palette.png")
            
            # Générer palette
            (
                ffmpeg
                .input(file_path, ss=start_time, t=duration)
                .filter('fps', fps=fps)
                .filter('scale', width, -1, flags='lanczos')
                .filter('split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer')
                .output(palette_path)
                .overwrite_output()
                .run(quiet=True)
            )
            
            logger.info(f"✅ GIF preview créé: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Erreur création GIF: {e}")
            return None


# Instance globale
video_processor = VideoProcessor()


def get_video_info(file_path: str) -> Dict[str, Any]:
    """
    Fonction utilitaire rapide pour obtenir les infos d'une vidéo
    
    Args:
        file_path: Chemin du fichier
    
    Returns:
        dict: Informations de la vidéo
    """
    metadata = video_processor.extract_metadata(file_path)
    return {
        'duration': metadata.duration,
        'width': metadata.width,
        'height': metadata.height,
        'resolution': metadata.resolution,
        'is_hd': metadata.is_hd,
        'bitrate': metadata.bitrate,
        'format': metadata.format_name
    }
