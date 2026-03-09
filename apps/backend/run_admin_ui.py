from app.admin_ui import admin_app

# Local-only admin dashboard. Only people with source code can run this.
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(admin_app, host="127.0.0.1", port=8010)
