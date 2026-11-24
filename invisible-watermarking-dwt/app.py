"""Titik masuk dashboard web.  Jalankan:  python app.py"""
from webapp import create_app
from config import Config

app = create_app()

if __name__ == "__main__":
    print(f"\n  Dashboard Watermarking DWT  ->  http://{Config.HOST}:{Config.PORT}\n")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
