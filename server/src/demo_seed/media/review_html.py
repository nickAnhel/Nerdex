from __future__ import annotations

from pathlib import Path

from src.demo_seed.media.cache_index import CacheIndex


def generate_media_review_html(cache_index: CacheIndex, output_path: Path) -> Path:
    rows: list[str] = []
    grouped = sorted(cache_index.items, key=lambda item: (item.topic, item.role, item.provider_item_id))
    for item in grouped:
        file_path = Path(item.local_path)
        exists = file_path.exists()
        preview = ""
        if item.media_type == "image" and exists:
            preview = f'<img src="{file_path.as_posix()}" style="max-width:220px;max-height:130px;object-fit:cover;" />'
        elif item.media_type == "video" and exists:
            preview = f'<video src="{file_path.as_posix()}" controls style="max-width:220px;max-height:130px;"></video>'
        else:
            preview = "missing"

        rows.append(
            "<tr>"
            f"<td>{item.topic}</td>"
            f"<td>{item.role}</td>"
            f"<td>{item.query}</td>"
            f"<td>{item.provider_item_id}</td>"
            f"<td>{item.media_type}</td>"
            f"<td>{item.width or ''}x{item.height or ''}</td>"
            f"<td>{item.duration_seconds or ''}</td>"
            f"<td>{item.orientation or ''}</td>"
            f"<td>{item.size_bytes}</td>"
            f"<td>{'yes' if exists else 'no'}</td>"
            f"<td><code>{item.local_path}</code></td>"
            f"<td>{preview}</td>"
            "</tr>"
        )

    html = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Demo Seed Media Review</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 18px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #ddd; padding: 6px; vertical-align: top; }
    th { background: #f5f5f5; }
    code { font-size: 11px; }
  </style>
</head>
<body>
  <h1>Demo Seed Media Review</h1>
  <table>
    <thead>
      <tr>
        <th>Topic</th><th>Role</th><th>Query</th><th>Provider ID</th><th>Type</th>
        <th>Dimensions</th><th>Duration</th><th>Orientation</th><th>Size (bytes)</th>
        <th>Exists</th><th>Local Path</th><th>Preview</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>""".replace("{rows}", "\n".join(rows))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
