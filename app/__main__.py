import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description='Run the local quant research application')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    # Single process. The bundled queue is deliberately local, not distributed.
    uvicorn.run('app.main:app', host='127.0.0.1', port=args.port, workers=1)

if __name__ == '__main__':
    main()
