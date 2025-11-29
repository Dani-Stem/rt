from backend import create_app

app = create_app()

# Runs the app
if __name__ == "__main__":
    app.run(host="localhost", port=8000, debug=True)
