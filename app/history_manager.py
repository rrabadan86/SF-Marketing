import json
import sqlite3
from datetime import datetime


DB_FILE = (
    "/app/data/creative_agent.db"
)


def get_conn():
    conn = sqlite3.connect(
        DB_FILE
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS creatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creative_code TEXT UNIQUE,

            parent_code TEXT,
            revision_type TEXT,

            request TEXT NOT NULL,
            briefing TEXT,

            source_photo_id TEXT,
            source_photo_name TEXT,
            source_photo_folder TEXT,

            quality_score REAL,
            brand_fit_score REAL,

            family TEXT,
            layout TEXT,
            background_style TEXT,

            headline TEXT,
            support_text TEXT,
            cta_text TEXT,
            badge_text TEXT,
            render_overrides_json TEXT,

            final_filename TEXT,
            drive_file_id TEXT,
            drive_link TEXT,

            logo_name TEXT,
            logo_type TEXT,
            logo_position TEXT,

            status TEXT DEFAULT 'PENDING',

            created_at TEXT,
            updated_at TEXT
        )
    """)

    existentes = [
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(creatives)"
        ).fetchall()
    ]

    novas_colunas = {
        "parent_code": "TEXT",
        "revision_type": "TEXT",
        "family": "TEXT",
        "layout": "TEXT",
        "background_style": "TEXT",

        # Estado textual efetivamente renderizado.
        "headline": "TEXT",
        "support_text": "TEXT",
        "cta_text": "TEXT",
        "badge_text": "TEXT",

        # Estado visual adicional, por exemplo:
        # {"support_font_delta": 2}
        "render_overrides_json": "TEXT",
    }

    for nome, tipo in novas_colunas.items():
        if nome not in existentes:
            conn.execute(
                f"""
                ALTER TABLE creatives
                ADD COLUMN {nome} {tipo}
                """
            )

    conn.commit()

    return conn


def gerar_codigo(
    creative_id,
):
    return (
        f"CRIATIVO-{creative_id:04d}"
    )


def registrar_criativo(
    request,
    briefing,
    photo,
    publication,
    family=None,
    layout=None,
    background_style=None,
    parent_code=None,
    revision_type="ORIGINAL",
    copy=None,
    badge_text=None,
    render_overrides=None,
):
    conn = get_conn()

    agora = datetime.now().isoformat(
        timespec="seconds"
    )

    copy = (
        copy
        or {}
    )

    render_overrides = (
        render_overrides
        or {}
    )

    render_overrides_json = json.dumps(
        render_overrides,
        ensure_ascii=False,
        sort_keys=True,
    )

    cursor = conn.execute("""
        INSERT INTO creatives (
            parent_code,
            revision_type,

            request,
            briefing,

            source_photo_id,
            source_photo_name,
            source_photo_folder,

            quality_score,
            brand_fit_score,

            family,
            layout,
            background_style,

            headline,
            support_text,
            cta_text,
            badge_text,
            render_overrides_json,

            final_filename,
            drive_file_id,
            drive_link,

            logo_name,
            logo_type,
            logo_position,

            status,
            created_at,
            updated_at
        )
        VALUES (
            ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?
        )
    """, (
        parent_code,
        revision_type,

        request,
        briefing,

        photo.get(
            "drive_file_id"
        ),
        photo.get(
            "filename"
        ),
        photo.get(
            "folder"
        ),

        photo.get(
            "quality_score"
        ),
        photo.get(
            "brand_fit_score"
        ),

        family,
        layout,
        background_style,

        copy.get(
            "headline"
        ),
        copy.get(
            "support"
        ),
        copy.get(
            "cta"
        ),
        badge_text,
        render_overrides_json,

        publication.get(
            "filename"
        ),
        publication.get(
            "drive_file",
            {},
        ).get(
            "id"
        ),
        publication.get(
            "drive_file",
            {},
        ).get(
            "webViewLink"
        ),

        publication.get(
            "logo_name"
        ),
        publication.get(
            "logo_type"
        ),
        publication.get(
            "logo_position"
        ),

        "PENDING",
        agora,
        agora,
    ))

    creative_id = (
        cursor.lastrowid
    )

    creative_code = gerar_codigo(
        creative_id
    )

    conn.execute("""
        UPDATE creatives
        SET creative_code = ?
        WHERE id = ?
    """, (
        creative_code,
        creative_id,
    ))

    conn.commit()
    conn.close()

    return creative_code


def buscar_criativo(
    creative_code,
):
    conn = get_conn()

    conn.row_factory = sqlite3.Row

    row = conn.execute("""
        SELECT *
        FROM creatives
        WHERE creative_code = ?
    """, (
        creative_code.upper(),
    )).fetchone()

    conn.close()

    if not row:
        return None

    item = dict(
        row
    )

    render_json = (
        item.get(
            "render_overrides_json"
        )
        or ""
    )

    try:
        item[
            "render_overrides"
        ] = (
            json.loads(
                render_json
            )
            if render_json
            else {}
        )

    except Exception:
        item[
            "render_overrides"
        ] = {}

    return item


def atualizar_status(
    creative_code,
    status,
):
    conn = get_conn()

    agora = datetime.now().isoformat(
        timespec="seconds"
    )

    cursor = conn.execute("""
        UPDATE creatives
        SET
            status = ?,
            updated_at = ?
        WHERE creative_code = ?
    """, (
        status,
        agora,
        creative_code.upper(),
    ))

    conn.commit()

    alterados = cursor.rowcount

    conn.close()

    return alterados > 0


def listar_ultimos(
    limite=10,
):
    conn = get_conn()

    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT *
        FROM creatives
        ORDER BY id DESC
        LIMIT ?
    """, (
        limite,
    )).fetchall()

    conn.close()

    resultado = []

    for row in rows:
        item = dict(
            row
        )

        render_json = (
            item.get(
                "render_overrides_json"
            )
            or ""
        )

        try:
            item[
                "render_overrides"
            ] = (
                json.loads(
                    render_json
                )
                if render_json
                else {}
            )

        except Exception:
            item[
                "render_overrides"
            ] = {}

        resultado.append(
            item
        )

    return resultado
