# app/services/generator_service.py
import google.generativeai as genai
from google import genai as google_genai  # New SDK for video generation
from google.genai import types
from google.api_core import exceptions
from app.config import settings
import json
import re
import os
from PIL import Image
from io import BytesIO
import uuid
import time
import logging
from urllib.parse import urlparse
import requests
from PIL import ImageDraw, ImageFont
from app.services import r2_service
from app.services.r2_service import download_bytes_from_r2_url

# Set up logging for better debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Service Configuration ---
try:
    if settings.GOOGLE_STUDIO_API_KEY:
        genai.configure(api_key=settings.GOOGLE_STUDIO_API_KEY)
        logger.info("✅ Google AI (Gemini) service configured successfully.")
    else:
        logger.warning("⚠️ WARNING: GOOGLE_STUDIO_API_KEY not found. Generation will use mocks.")
except Exception as e:
    logger.error(f"❌ Error configuring Google AI service: {e}")


# --- AI Model Helper Functions ---


def _call_gemini_for_json(system_prompt: str, user_prompt: str) -> dict:
    """
    Generates JSON output (captions) from Gemini API.
    Updated to use gemini-pro for JSON mode.
    """
    if not settings.GOOGLE_STUDIO_API_KEY:
        logger.info("🔧 Using mock captions (no API key)")
        return {"captions": [f"Mock caption for '{user_prompt}' 1", "Mock caption 2"]}

    try:
        logger.info(f"📝 Calling Gemini API for JSON generation with prompt: '{user_prompt[:50]}...'")

        # Use gemini-2.5-flash which supports JSON mode
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_prompt
        )

        response = model.generate_content(
            user_prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )

        result = json.loads(response.text)
        logger.info(f"✅ Successfully generated {len(result.get('captions', []))} captions")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing error: {e}")
        logger.error(f"Response text: {response.text if 'response' in locals() else 'No response'}")
        return {"captions": [f"Error: Invalid JSON response"]}


def _describe_image_with_gemini(image_path: str) -> str:
    """
    Uses Gemini vision to describe an image for contextual prompts.
    """
    # If input is a URL, download it first to a temp location
    try:
        if image_path.startswith('http://') or image_path.startswith('https://'):
            logger.info(f"🔽 Downloading image from URL for description: {image_path}")
            try:
                # Check if it's an R2 URL and use boto3 download if so
                if 'r2.cloudflarestorage.com' in image_path:
                    image_bytes = download_bytes_from_r2_url(image_path)
                else:
                    resp = requests.get(image_path, timeout=15)
                    resp.raise_for_status()
                    image_bytes = resp.content

                temp_image_dir = "app/frontend/temp_generated_images"
                os.makedirs(temp_image_dir, exist_ok=True)
                filename = f"{uuid.uuid4()}.png"
                local_path = os.path.join(temp_image_dir, filename)
                with open(local_path, "wb") as f:
                    f.write(image_bytes)
                image_path = local_path
            except Exception as e:
                logger.warning(f"⚠️ Failed to download image for description: {e}")
                # Try fallback to Google Drive if available (assuming file_id in URL or something, but for now generic)
                try:
                    # If it's a Drive URL, extract file_id and download via Drive
                    if 'drive.google.com' in image_path or 'docs.google.com' in image_path:
                        from app.services.google_drive import download_file_bytes
                        # Extract file_id from URL (e.g., https://drive.google.com/uc?export=download&id=FILE_ID)
                        parsed = urlparse(image_path)
                        query_params = dict(q.split('=') for q in parsed.query.split('&') if '=' in q)
                        file_id = query_params.get('id')
                        if file_id:
                            drive_data = download_file_bytes(file_id)
                            temp_image_dir = "app/frontend/temp_generated_images"
                            os.makedirs(temp_image_dir, exist_ok=True)
                            filename = f"{uuid.uuid4()}.png"
                            local_path = os.path.join(temp_image_dir, filename)
                            with open(local_path, "wb") as f:
                                f.write(drive_data['bytes'])
                            image_path = local_path
                        else:
                            raise ValueError("No file_id in Drive URL")
                    else:
                        raise e  # Re-raise original exception if not Drive
                except Exception as fallback_e:
                    logger.warning(f"⚠️ Fallback download also failed: {fallback_e}")
                    # Fall back to returning a generic description when download fails
                    return "Previous image unavailable — continue the story from the original prompt."

        if not settings.GOOGLE_STUDIO_API_KEY:
            logger.info("🔧 Using mock description (no API key)")
            # Provide a minimal, plausible description based on filename
            try:
                name = os.path.basename(image_path)
                return f"A visually simple image titled {name}, continuing the requested theme."
            except Exception:
                return "Mock description of the previous image."

        logger.info(f"🔍 Describing image: {image_path}")
        # Use Gemini 2.5 Flash Image capable model for vision tasks
        model = genai.GenerativeModel(model_name='gemini-2.5-flash-image')
        img = Image.open(image_path)
        response = model.generate_content(["Describe this image in detail for use in creating a sequential story or carousel.", img])
        description = response.text.strip()
        logger.info(f"✅ Image described: {description[:100]}...")
        return description
    except Exception as e:
        logger.error(f"❌ Error describing image: {e}")
        return "Description unavailable."


def _generate_single_image(prompt: str) -> str:
    """
    Generates a single image using the Imagen 2 model.
    """
    if not settings.GOOGLE_STUDIO_API_KEY:
        # Mock fallback: create a local placeholder image and save it so carousel can describe it
        try:
            temp_image_dir = "app/frontend/temp_generated_images"
            os.makedirs(temp_image_dir, exist_ok=True)
            filename = f"{uuid.uuid4()}.png"
            path = os.path.join(temp_image_dir, filename)

            # Create a simple placeholder image with the prompt text
            img = Image.new('RGB', (1080, 1080), color=(240, 240, 240))
            draw = ImageDraw.Draw(img)
            text = re.sub(r'\s+', ' ', re.sub(r'[^\x00-\x7F]', '', prompt))[:200]
            try:
                # Use a default font; ImageFont may fall back if a TTF isn't available
                font = ImageFont.load_default()
            except Exception:
                font = None
            # Wrap text roughly
            margin = 40
            offset = 40
            if font:
                draw.text((margin, offset), text, fill=(20, 20, 20), font=font)
            else:
                draw.text((margin, offset), text, fill=(20, 20, 20))

            img.save(path)
            # If R2 configured, upload and return R2 URL; otherwise return local relative path
            try:
                if settings.CLOUDFLARE_R2_BUCKET and settings.CLOUDFLARE_R2_ENDPOINT:
                    r2_info = r2_service.upload_file_to_r2(path, key_prefix='temp_generated_images', public=False)
                    logger.info(f"🔧 Mock image uploaded to R2: {r2_info.get('url')}")
                    return r2_info.get('url')
            except Exception as e:
                logger.warning(f"Failed to upload mock image to R2: {e}")

            relative_url = f"/temp_generated_images/{filename}"
            logger.info(f"🔧 Mock image saved: {relative_url}")
            return relative_url
        except Exception as e:
            logger.error(f"❌ Failed to create mock image: {e}")
            safe_prompt = re.sub(r'[^a-zA-Z0-9 ]', '', prompt)
            return f"https://via.placeholder.com/1080x1080.png?text=Image+{safe_prompt}"

    try:
        # Be more explicit with the prompt for image generation
        image_prompt = f"Visually stunning image, ultra-realistic, 8k, for a social media post about: {prompt}"
        logger.info(f"🎨 Generating single image with prompt: '{image_prompt[:50]}...'")
        # Use Gemini 2.5 Flash Image model for image generation
        model = genai.GenerativeModel(model_name='gemini-2.5-flash-image')
        temp_image_dir = "app/frontend/temp_generated_images"
        os.makedirs(temp_image_dir, exist_ok=True)

        response = None
        retries = 3
        for i in range(retries):
            try:
                response = model.generate_content(image_prompt)
                break  # Success
            except exceptions.InternalServerError as e:
                if i < retries - 1:
                    logger.warning(f"⚠️ Internal server error. Retrying in 5 seconds... ({i + 1}/{retries - 1})")
                    time.sleep(5)
                else:
                    logger.error("❌ Internal server error after multiple retries.")
                    raise e

        if not response:
            return ""

        # Extract image data
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                img = Image.open(BytesIO(part.inline_data.data))
                filename = f"{uuid.uuid4()}.png"
                path = os.path.join(temp_image_dir, filename)
                img.save(path)
                # If R2 configured, upload the generated image and return the public R2 URL for frontend
                try:
                    if settings.CLOUDFLARE_R2_BUCKET and settings.CLOUDFLARE_R2_ENDPOINT:
                        r2_info = r2_service.upload_file_to_r2(path, key_prefix='generated_images', public=True)
                        r2_url = r2_info.get('url')
                        logger.info(f"✅ Image uploaded to R2: {r2_url}")
                        # Keep local copy for UI display, but return R2 URL for tracking
                        return r2_url
                except Exception as e:
                    logger.warning(f"Failed to upload generated image to R2: {e}")

                # Fallback: Return relative URL for frontend access if R2 upload fails
                relative_url = f"/temp_generated_images/{filename}"
                logger.info(f"✅ Image saved locally: {filename}")
                return relative_url

        logger.warning("⚠️ No image data in response")
        if response.prompt_feedback:
            logger.warning(f"    Reason: {response.prompt_feedback}")
        else:
            logger.warning(f"    Response: {response.text}")
        return ""

    except Exception as e:
        logger.error(f"❌ Critical error in single image generation: {e}", exc_info=True)
        return ""


def _call_imagen_for_images(prompt: str, count: int) -> list:
    """
    Uses the Gemini 2.5 Flash Image model (via _generate_single_image) to generate images.
    Delegates to `_generate_single_image` for both real and mock paths so generated media
    are consistently saved/returned as relative URLs usable by the rest of the app.
    """
    try:
        logger.info(f"🎨 Generating {count} images with Gemini 2.5 Flash Image (via _generate_single_image)")
        image_urls = []

        for i in range(count):
            logger.info(f"🖼️ Generating image {i+1}/{count}...")
            url = _generate_single_image(prompt)
            if url:
                image_urls.append(url)
            else:
                logger.warning(f"⚠️ Failed to generate image {i+1}")

        logger.info(f"✅ Generated {len(image_urls)}/{count} images")
        return image_urls

    except Exception as e:
        logger.error(f"❌ Critical error in image generation: {e}", exc_info=True)
        return []

def _call_veo_for_video(prompt: str) -> str:
    """
    Uses Veo model to generate videos.
    Updated to use the correct Google GenAI SDK for video generation.
    """
    if not settings.GOOGLE_STUDIO_API_KEY:
        logger.info("🔧 Using mock video (no API key)")
        return "https://www.w3schools.com/html/mov_bbb.mp4"

    try:
        logger.info(f"🎬 Generating video with Veo")
        logger.info(f"Prompt: '{prompt[:100]}...'")
        
        client = google_genai.Client(api_key=settings.GOOGLE_STUDIO_API_KEY)
        
        operation = client.models.generate_videos(
            model="veo-3.1-generate-preview",
            prompt=prompt,
        )
        
        logger.info("⏳ Video generation started. Waiting for completion...")
        logger.info(f"Operation name: {operation.name}")
        
        poll_count = 0
        max_polls = 60
        
        while not operation.done:
            poll_count += 1
            logger.info(f"⏳ Polling... ({poll_count}/{max_polls}) - Status: {operation.done}")
            
            if poll_count >= max_polls:
                logger.error("❌ Video generation timeout (10 minutes)")
                return "Error: Video generation timeout"
            
            time.sleep(10)
            operation = client.operations.get(operation)
        
        logger.info("✅ Video generation complete!")
        
        generated_video = operation.response.generated_videos[0]
        logger.info(f"Video URI: {generated_video.video.uri if hasattr(generated_video.video, 'uri') else 'N/A'}")
        
        temp_video_dir = "app/frontend/temp_generated_videos"
        os.makedirs(temp_video_dir, exist_ok=True)
        logger.info(f"📁 Temporary video directory: {temp_video_dir}")

        filename = f"{uuid.uuid4()}.mp4"
        video_path = os.path.join(temp_video_dir, filename)

        logger.info("⬇️ Downloading video...")
        video_file = client.files.download(file=generated_video.video)
        with open(video_path, "wb") as f:
            f.write(video_file)

        logger.info(f"✅ Video saved: {filename}")

        relative_url = f"/temp_generated_videos/{filename}"
        return relative_url
        
    except Exception as e:
        logger.error(f"❌ Error calling Veo API: {e}")
        logger.exception("Full traceback:")
        return f"Error generating video: {str(e)}"


# --- Public Service Functions ---


def generate_static_post(prompt: str, num_media: int):
    """
    Generates num_media images and 4 captions for a static post.
    """
    logger.info("=" * 80)
    logger.info("🚀 STARTING STATIC POST GENERATION")
    logger.info(f"Prompt: '{prompt}' | Num Media: {num_media}")
    logger.info("=" * 80)

    caption_system_prompt = settings.STATIC_POST_PROMPT

    try:
        media_urls = _call_imagen_for_images(prompt=prompt, count=num_media)
        caption_json = _call_gemini_for_json(system_prompt=caption_system_prompt, user_prompt=prompt)

        result = {
            "media": media_urls,
            "captions": caption_json.get("captions", ["Error or no captions."])
        }

        logger.info("✅ STATIC POST GENERATION COMPLETE")
        logger.info(f"Generated {len(result['media'])} images and {len(result['captions'])} captions")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error(f"❌ Error in generate_static_post: {e}")
        logger.exception("Full traceback:")
        return {"media": [], "captions": [f"Error: {str(e)}"]}


def generate_carousel_post(prompt: str, num_media: int):
    """
    Generates num_media images in sequential flow and 4 captions for a carousel post.
    Each subsequent image builds context from the previous one.
    """
    logger.info("=" * 80)
    logger.info("🚀 STARTING CAROUSEL POST GENERATION (SEQUENTIAL)")
    logger.info(f"Prompt: '{prompt}' | Num Media: {num_media}")
    logger.info("=" * 80)

    caption_system_prompt = settings.CAROUSEL_POST_PROMPT

    try:
        media_urls = []
        temp_image_dir = "app/frontend/temp_generated_images"
        os.makedirs(temp_image_dir, exist_ok=True)

        for i in range(num_media):
            if i == 0:
                # First image: use original prompt
                current_prompt = prompt
                logger.info(f"🖼️ Generating first image with original prompt")
            else:
                # Subsequent images: describe previous image (media_urls[-1]) and create contextual prompt
                try:
                    prev_media = media_urls[-1]
                    prev_description = _describe_image_with_gemini(prev_media)
                except Exception as e:
                    logger.warning(f"⚠️ Could not describe previous image: {e}")
                    prev_description = "Previous image unavailable — continue the story from the original prompt."

                current_prompt = f"This is a story about '{prompt}'. The previous scene was: '{prev_description}'. Create the next image in the story, continuing the theme of '{prompt}'."
                logger.info(f"🖼️ Generating image {i+1} with contextual prompt: '{current_prompt[:100]}...'")

            logger.info(f"Carousel step {i+1} prompt: {current_prompt}")
            url = _generate_single_image(current_prompt)
            if url:
                media_urls.append(url)
                logger.info(f"✅ Image {i+1} generated: {url}")
            else:
                logger.warning(f"⚠️ Failed to generate image {i+1}")
                break

        # After generating images, create descriptions for each media item to produce sequence-aware captions
        try:
            descriptions = []
            for idx, m in enumerate(media_urls):
                try:
                    desc = _describe_image_with_gemini(m)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to describe generated image {idx+1}: {e}")
                    desc = f"Slide {idx+1}: visual unavailable."
                descriptions.append(desc)

            # Build a combined prompt listing each slide description in order
            descriptions_text = "\n".join([f"{i+1}. {d}" for i, d in enumerate(descriptions)])
            caption_user_prompt = (
                f"The user asked for a carousel on: '{prompt}'.\n"
                f"Below are short descriptions of each generated slide in order:\n{descriptions_text}\n\n"
                "Using the system instructions, generate 4 unique captions that form a cohesive narrative arc for this carousel. "
                "Each caption should map to a slide in order (first caption -> first slide, etc.). If there are fewer than 4 slides, produce one caption per slide."
            )

            # Augment the system prompt at runtime to explicitly require mapping captions to slide descriptions
            augmented_system_prompt = (
                caption_system_prompt
                + "\n\nIMPORTANT: Use the slide descriptions provided in the user prompt to craft captions that are directly related to each slide's visual content."
                + " Ensure the output is a JSON object with a single key 'captions' whose value is an array of captions in the same order as the slides."
            )

            caption_json = _call_gemini_for_json(system_prompt=augmented_system_prompt, user_prompt=caption_user_prompt)
        except Exception as e:
            logger.error(f"❌ Failed to generate sequence-aware captions: {e}")
            # Fallback to original behavior
            caption_json = _call_gemini_for_json(system_prompt=caption_system_prompt, user_prompt=prompt)

        result = {
            "media": media_urls,
            "captions": caption_json.get("captions", ["Error or no captions."])
        }

        logger.info("✅ CAROUSEL POST GENERATION COMPLETE")
        logger.info(f"Generated {len(result['media'])} images and {len(result['captions'])} captions")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error(f"❌ Error in generate_carousel_post: {e}")
        logger.exception("Full traceback:")
        return {"media": [], "captions": [f"Error: {str(e)}"]}


def generate_video_post(prompt: str, num_media: int):
    """
    Generates num_media videos and 4 captions for a video post.
    """
    logger.info("=" * 80)
    logger.info("🚀 STARTING VIDEO POST GENERATION")
    logger.info(f"Prompt: '{prompt}' | Num Media: {num_media}")
    logger.info("=" * 80)

    caption_system_prompt = settings.VIDEO_POST_PROMPT

    try:
        media_urls = [_call_veo_for_video(prompt=prompt) for _ in range(num_media)]
        caption_json = _call_gemini_for_json(system_prompt=caption_system_prompt, user_prompt=prompt)

        result = {
            "media": media_urls,
            "captions": caption_json.get("captions", ["Error or no captions."])
        }

        logger.info("✅ VIDEO POST GENERATION COMPLETE")
        logger.info(f"Generated {len(result['media'])} videos and {len(result['captions'])} captions")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error(f"❌ Error in generate_video_post: {e}")
        logger.exception("Full traceback:")
        return {"media": [], "captions": [f"Error: {str(e)}"]}


def regenerate_item(prompt: str, post_type: str, index: int, media: list, regen_target: str, captions: list = []):
    """
    Regenerate a single media item or caption. For media, returns a new media URL that replaces media[index].
    For caption, returns either a single caption string or a refreshed captions list depending on post_type.
    """
    logger.info(f"🔁 Regenerating item: target={regen_target} index={index} post_type={post_type}")
    try:
        if regen_target == 'media':
            # Use the original prompt and index context to regenerate a single image
            if post_type == 'carousel' and index > 0 and media and len(media) > 0:
                # Build contextual prompt using previous slide if possible
                try:
                    prev = media[index-1]
                    prev_desc = _describe_image_with_gemini(prev)
                except Exception:
                    prev_desc = ''
                regen_prompt = f"This is a continuation of: '{prompt}'. The previous scene was: '{prev_desc}'. Create the next image in the story."
            else:
                regen_prompt = prompt

            new_url = _generate_single_image(regen_prompt)
            return {"media_url": new_url}

        elif regen_target == 'caption':
            # Regenerate only the caption at the specified index
            if post_type == 'carousel' and media:
                # Describe the specific media item at index
                try:
                    media_desc = _describe_image_with_gemini(media[index])
                except Exception:
                    media_desc = f"Slide {index+1}: visual unavailable."
                # Include existing captions to avoid duplicates
                existing_captions_text = "\n".join([f"- {c}" for c in captions if c])
                caption_user_prompt = (
                    f"The user asked for a carousel on: '{prompt}'.\n"
                    f"Description of slide {index+1}: {media_desc}\n\n"
                    f"Existing captions in this post:\n{existing_captions_text}\n\n"
                    f"Generate a single NEW caption for slide {index+1} that fits the overall theme of '{prompt}'. Make it completely different from the existing captions. Be creative, unique, and avoid generic phrases."
                )
                augmented_system_prompt = (
                    settings.CAROUSEL_POST_PROMPT
                    + "\n\nIMPORTANT: Generate only ONE caption for the specified slide. Output as JSON with key 'caption'. Make it unique and creative. Ensure it's different from any existing captions provided."
                )
                caption_json = _call_gemini_for_json(system_prompt=augmented_system_prompt, user_prompt=caption_user_prompt)
                return {"caption": caption_json.get('caption', 'Error generating caption')}
            else:
                # Static or single image: regenerate a single caption
                existing_captions_text = "\n".join([f"- {c}" for c in captions if c])
                caption_user_prompt = (
                    f"Generate a single NEW caption for: '{prompt}'. Make it different and creative. Be unique and avoid generic phrases.\n\n"
                    f"Existing captions in this post:\n{existing_captions_text}\n\n"
                    f"Ensure the new caption is completely different from the existing ones."
                )
                system_prompt = settings.STATIC_POST_PROMPT or "You are a creative social media caption generator. Generate engaging, unique captions for posts."
                caption_json = _call_gemini_for_json(system_prompt=system_prompt, user_prompt=caption_user_prompt)
                return {"caption": caption_json.get('caption', 'Error generating caption')}

        else:
            return {}
    except Exception as e:
        logger.error(f"❌ Error in regenerate_item: {e}")
        return {}
