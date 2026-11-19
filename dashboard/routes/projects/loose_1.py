from __future__ import annotations


# --- Loose-work approved folders (lane p5-prj, Project charter decisions 4 and 8) ---------------------------
# Without a project the artist's approved folders live server-side in one small JSON file (approved_roots.py,
# LooseWorkFolders). Only this page route writes it, from the page's own folder picker (commitApprovedRoots,
# no-project branch); it is not an agent tool and refuses caller "hermes". expected_revision null replaces the
# list as the page holds it (the page does not track the revision yet); an integer is compare-and-set.


class LooseFoldersWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: int | None = Field(default=None, ge=0)
    approved_roots: list[str] = Field(max_length=64)


@project_router.put("/projects/loose/folders")
async def projects_loose_folders(request: LooseFoldersWriteRequest) -> dict[str, Any]:
    if _film_caller() == "hermes":
        return _folder_refusal(hermes_decision=True)
    roots: list[str] = []
    for root in request.approved_roots:
        if _approved_roots_module.canonical(root) is None or not Path(root.strip()).is_dir():
            return {"error": {"code": "invalid_project", "message": "Project request is invalid"}}
        roots.append(root.strip())
    try:
        written = _loose_work_folders().write(list(dict.fromkeys(roots)), expected_revision=request.expected_revision)
    except _approved_roots_module.LooseConflict as exc:
        return {"error": {"code": "project_conflict", "message": "Project changed since this revision"}, "revision": exc.revision}
    except (OSError, ValueError):
        return {"error": {"code": "project_io_failed", "message": "Project could not be saved"}}
    return {"revision": written["revision"], "approved_roots": written["approved_roots"]}


# --- Folder grants taken back (lane w41-safe, MED-102) -------------------------------------------------------------
# The host keeps the folders the artist granted Continuo (Hermes Settings > Plugins > Folder access) where the backend
# cannot read them. The page reports the host's current list on start, after a grant and while it is open; a folder
# granted before and missing now is revoked for every route (_request_roots) until a report holds it again. Page only:
# Hermes cannot grant or revoke (refused folder_not_approved, like the Loose-work list).
class FolderGrantsReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    granted: list[str] = Field(max_length=256)


@project_router.put("/projects/folder-grants")
async def projects_folder_grants(request: FolderGrantsReport) -> dict[str, Any]:
    if _film_caller() == "hermes":
        return _folder_refusal(hermes_decision=True)
    try:
        document = await asyncio.to_thread(_folder_grants().report, request.granted)
    except (OSError, ValueError):
        return {"error": {"code": "project_io_failed", "message": "Project could not be saved"}}
    return {"granted": document["granted"], "revoked": document["revoked"]}
