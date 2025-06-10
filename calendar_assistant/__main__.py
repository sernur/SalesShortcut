#!/usr/bin/env python3
"""Calendar Assistant placeholder service"""

if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI()
    
    @app.get("/")
    def read_root():
        return {"message": "Calendar Assistant service - placeholder"}
    
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "service": "calendar_assistant"}
    
    print("Starting Calendar Assistant placeholder service on port 8080...")
    uvicorn.run(app, host="0.0.0.0", port=8080)