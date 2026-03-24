import json
from pathlib import Path
from apps.brainatlas.backend.app.services.registration_service import hydrate_global_registration, discover_project_global

out = Path(r"E:\workspace\brainatlas\data\temp\hydrate_debug.json")
out.parent.mkdir(parents=True, exist_ok=True)

result = {
    "discover_project_global": discover_project_global("default"),
    "hydrate_c44": hydrate_global_registration("c44faa871b5a"),
    "hydrate_889": hydrate_global_registration("889dc4ba65ed"),
}
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(str(out))
