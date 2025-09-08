import uvicorn
from .api import middleware_api

def main():
    uvicorn.run(middleware_api.app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()