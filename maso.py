import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timedelta

# --- 設定 ---
import os

TOKEN = os.getenv("TOKEN")

# チャンネルID設定（すべて整数で入力してください）
TEXT_NOTIFY_CHANNEL_ID = 1505413456403370106  # 入退室の通知を流すテキストチャンネルのID
VC_FOCUS_ID = 1462792432927244378        # 【集中用】自習VCのID
VC_CHAT_ID = 1456955244498915342            # 【雑談用】自習VCのID

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command('help')

# VC入室時間を一時記録する辞書
vc_timers = {}

# --- データベース処理 ---
def init_db():
    conn = sqlite3.connect('study_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_logs (
            user_id INTEGER, date TEXT, subject TEXT, minutes INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def add_study_time(user_id, subject, minutes):
    conn = sqlite3.connect('study_data.db')
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('INSERT INTO study_logs VALUES (?, ?, ?, ?)', (user_id, today, subject, minutes))
    conn.commit()
    conn.close()

def get_total_minutes(user_id, start_date):
    conn = sqlite3.connect('study_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(minutes) FROM study_logs WHERE user_id = ? AND date >= ?', (user_id, start_date.strftime('%Y-%m-%d')))
    result = cursor.fetchone()[0]
    conn.close()
    return result if result else 0

def get_ranking_data(start_date):
    conn = sqlite3.connect('study_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, SUM(minutes) FROM study_logs WHERE date >= ? GROUP BY user_id ORDER BY SUM(minutes) DESC', (start_date.strftime('%Y-%m-%d'),))
    results = cursor.fetchall()
    conn.close()
    return results

# --- Bot起動イベント ---
@bot.event
async def on_ready():
    init_db()
    print(f'🔥 {bot.user.name} が正常に起動しました！')



# --- コマンド処理 ---
@bot.command(name='record')
async def record(ctx, subject: str, minutes: int):
    if minutes <= 0: return
    add_study_time(ctx.author.id, subject, minutes)
    await ctx.send(f"✅ {ctx.author.mention} さんの記録を保存しました！\n**【{subject}】: {minutes}分**")

@bot.command(name='status')
async def status(ctx):
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    today_time = get_total_minutes(ctx.author.id, today_start)
    week_time = get_total_minutes(ctx.author.id, week_start)
    month_time = get_total_minutes(ctx.author.id, month_start)

    embed = discord.Embed(title=f"📊 {ctx.author.display_name} さんの勉強状況", color=0x00ffcc)
    embed.add_field(name="📅 今日", value=f"`{today_time // 60}時間 {today_time % 60}分` ({today_time}分)", inline=False)
    embed.add_field(name="📅 今週 (月曜から)", value=f"`{week_time // 60}時間 {week_time % 60}分` ({week_time}分)", inline=False)
    embed.add_field(name="📅 今月", value=f"`{month_time // 60}時間 {month_time % 60}分` ({month_time}分)", inline=False)
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='ranking')
async def ranking(ctx, period: str):
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'week':
        start_date = today_start - timedelta(days=now.weekday())
        title_text = "🏆 週間勉強時間ランキング"
    elif period == 'month':
        start_date = today_start.replace(day=1)
        title_text = "🏆 月間勉強時間ランキング"
    else:
        await ctx.send("❌ `!ranking week` または `!ranking month` と入力してください。")
        return

    ranking_list = get_ranking_data(start_date)
    if not ranking_list:
        await ctx.send("📅 データがまだありません。")
        return

    embed = discord.Embed(title=title_text, color=0xffd700)
    medal_emojis = ["🥇", "🥈", "🥉"]
    description = ""
    for index, (user_id, total_min) in enumerate(ranking_list[:10]):
        member = ctx.guild.get_member(user_id)
        name = member.display_name if member else f"ユーザー({user_id})"
        emoji = medal_emojis[index] if index < 3 else f"【{index + 1}位】"
        description += f"{emoji} **{name}**: {total_min // 60}時間{total_min % 60}分 ({total_min}分)\n"
    embed.description = description
    await ctx.send(embed=embed)

@bot.command(name='studyhelp')
async def studyhelp(ctx):
    embed = discord.Embed(title="📖 勉強用Bot コマンド一覧", description="このBotで使えるコマンドと自習室の使い方です。", color=0x3498db)
    embed.add_field(name="📝 1. 勉強内容を直接記録する", value="`!record <教科名> <分数>`\n（例： `!record 数学 60` ）", inline=False)
    embed.add_field(name="📊 2. 自分の勉強時間を確認する", value="`!status`", inline=False)
    embed.add_field(name="🏆 3. 勉強時間ランキングを見る", value="`!ranking week` / `!ranking month`", inline=False)
    embed.add_field(name="🔊 4. 自習室の使い方", value="・**【集中自習室】**：入室すると強制ミュート（スピーカーも）\n・**【雑談自習室】**：ミュートなし通話可能\n※退室時に自動集計されます。", inline=False)
    await ctx.send(embed=embed)

bot.run(TOKEN)
