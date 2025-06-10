#!/usr/bin/env python3
"""Lead Finder placeholder service"""

if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI()
    
    @app.get("/")
    def read_root():
        return {"message": "Lead Finder service - placeholder"}
    
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "service": "lead_finder"}
    
    print("Starting Lead Finder placeholder service on port 8081...")
    uvicorn.run(app, host="0.0.0.0", port=8081)