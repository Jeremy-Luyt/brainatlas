import uvicorn


if __name__ == "__main__":
    uvicorn.run("apps.brainatlas.backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
