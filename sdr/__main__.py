#!/usr/bin/env python3
"""SDR placeholder service"""

if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI()
    
    @app.get("/")
    def read_root():
        return {"message": "SDR service - placeholder"}
    
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "service": "sdr"}
    
    print("Starting SDR placeholder service on port 8084...")
    uvicorn.run(app, host="0.0.0.0", port=8084)