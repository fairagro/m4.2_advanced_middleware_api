import uvicorn
from .api import middleware_api

def main():
    uvicorn.run(
        middleware_api.app,
        host=middleware_api.listen_addr,
        port=middleware_api.listen_port)

if __name__ == "__main__":
    main()