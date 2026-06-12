"""
Test script to decode and verify JWT tokens
Usage: python test_jwt.py YOUR_TOKEN_HERE
"""
import sys
from jose import jwt, JWTError
from datetime import datetime

def decode_token_debug(token: str, secret_key: str):
    """Debug JWT token decoding"""
    print("=" * 80)
    print("JWT TOKEN DEBUG")
    print("=" * 80)
    
    # Decode header without verification
    try:
        unverified_header = jwt.get_unverified_header(token)
        print(f"\n✓ Token Header (unverified):")
        for key, value in unverified_header.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"\n✗ Failed to decode header: {e}")
        return
    
    # Decode claims without verification
    try:
        unverified_claims = jwt.get_unverified_claims(token)
        print(f"\n✓ Token Claims (unverified):")
        for key, value in unverified_claims.items():
            if key == "exp":
                exp_time = datetime.fromtimestamp(value)
                is_expired = exp_time < datetime.now()
                print(f"  {key}: {value} ({exp_time}) {'[EXPIRED!]' if is_expired else '[Valid]'}")
            else:
                print(f"  {key}: {value}")
    except Exception as e:
        print(f"\n✗ Failed to decode claims: {e}")
        return
    
    # Try to verify with provided secret
    print(f"\n🔑 Verifying with secret key: {secret_key[:20]}...")
    try:
        algorithm = unverified_header.get("alg", "HS256")
        verified_claims = jwt.decode(token, secret_key, algorithms=[algorithm])
        print(f"✓ Token verified successfully with {algorithm}!")
        
        # Check for user identifier
        user_id = verified_claims.get('sub') or verified_claims.get('user_id')
        if user_id:
            print(f"  ✓ User ID: {user_id}")
            if verified_claims.get('sub'):
                print(f"    (from 'sub' claim - JWT standard)")
            else:
                print(f"    (from 'user_id' claim - custom)")
        else:
            print(f"  ✗ WARNING: No user identifier found!")
            print(f"    Missing both 'sub' and 'user_id' claims")
            print(f"    Available claims: {list(verified_claims.keys())}")
        
        # Show other important claims
        if verified_claims.get('username'):
            print(f"  ✓ Username: {verified_claims.get('username')}")
        if verified_claims.get('email'):
            print(f"  ✓ Email: {verified_claims.get('email')}")
            
    except jwt.ExpiredSignatureError:
        print(f"✗ Token has EXPIRED")
    except jwt.JWTClaimsError as e:
        print(f"✗ Invalid claims: {e}")
    except JWTError as e:
        print(f"✗ Verification failed: {type(e).__name__}: {e}")
        print(f"\n💡 This usually means:")
        print(f"   1. The SECRET_KEY is wrong (doesn't match the auth service)")
        print(f"   2. The algorithm is wrong")
        print(f"   3. The token was signed with a different key")
    
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_jwt.py YOUR_TOKEN_HERE")
        print("\nExample:")
        print("  python test_jwt.py eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        sys.exit(1)
    
    token = sys.argv[1]
    
    # Read secret from .env.local
    import os
    from pathlib import Path
    
    # Try to find .env.local
    env_file = Path(__file__).parent.parent.parent.parent / "config" / "environments" / ".env.local"
    
    secret_key = "your-jwt-secret-key-change-in-production"  # Default
    
    if env_file.exists():
        print(f"Reading config from: {env_file}")
        with open(env_file) as f:
            for line in f:
                if line.startswith("SECRET_KEY="):
                    secret_key = line.split("=", 1)[1].strip()
                    break
        print(f"Found SECRET_KEY: {secret_key[:20]}...\n")
    else:
        print(f"Warning: Could not find .env.local at {env_file}")
        print(f"Using default SECRET_KEY\n")
    
    decode_token_debug(token, secret_key)
