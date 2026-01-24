import nextcord as discord
from database import db
from utils.tafsir import fetch_page_tafsir, format_tafsir, TAFSIR_EDITIONS
from utils.translation import fetch_page_translations, format_translations
from utils.pagination import paginate_text
from views import TafsirView, TranslationView


async def handle_tafsir(interaction: discord.Interaction, page_number: int):
    """Handle tafsir button interaction"""
    from database import db
    from utils.tafsir import fetch_page_tafsir, format_tafsir, TAFSIR_EDITIONS
    from utils.pagination import paginate_text

    # Get user's tafsir preference
    tafsir_edition = await db.get_user_tafsir_preference(interaction.user.id, interaction.guild_id)

    # Fetch tafsir
    tafsir_data = await fetch_page_tafsir(page_number, tafsir_edition)
    if tafsir_data is None:
        await interaction.response.send_message("❌ Failed to fetch tafsir. Please try again later.", ephemeral=True)
        return

    formatted_text = await format_tafsir(tafsir_data)
    pages = paginate_text(formatted_text)

    # Create the tafsir view with edition selector and pagination
    view = TafsirView(page_number, tafsir_edition, pages, 0, len(tafsir_data))

    embed = discord.Embed(
        title=f"📚 Page {page_number} Tafsir ({len(tafsir_data)} ayahs)",
        description=pages[0],
        color=discord.Color.green()
    )
    if len(pages) > 1:
        embed.set_footer(text=f"Page 1 of {len(pages)}")

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def handle_translation(interaction: discord.Interaction, page_number: int):
    """Handle translation button interaction"""
    from database import db
    from utils.translation import fetch_page_translations, format_translations
    from utils.pagination import paginate_text

    # Get user's language preference
    language = await db.get_user_language_preference(interaction.user.id, interaction.guild_id)

    # Fetch translations
    translations = await fetch_page_translations(page_number, language)
    if translations is None:
        await interaction.response.send_message("❌ Failed to fetch translations. Please try again later.", ephemeral=True)
        return

    formatted_text = await format_translations(translations)
    pages = paginate_text(formatted_text)

    # Create the translation view with language selector and pagination
    view = TranslationView(page_number, language, pages)

    embed = discord.Embed(
        title=f"📖 Page {page_number} Translation",
        description=pages[0],
        color=discord.Color.blue()
    )
    if len(pages) > 1:
        embed.set_footer(text=f"Page 1 of {len(pages)}")

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)