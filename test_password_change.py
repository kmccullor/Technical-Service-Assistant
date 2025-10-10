#!/usr/bin/env python3
"""
Test Password Change Requirements

Test script to verify that users must change passwords on first login.
"""

import requests
import json

BASE_URL = "http://localhost:8008/api/auth"

def test_login_with_password_change_required():
    """Test login for user who needs to change password"""
    print("🧪 Testing Login with Password Change Required")
    print("=" * 60)
    
    # Test Kevin's login
    login_data = {
        "email": "kevin.mccullor@xylem.com",
        "password": "password123"
    }
    
    response = requests.post(f"{BASE_URL}/login", json=login_data)
    
    if response.status_code == 200:
        data = response.json()
        user = data.get('user', {})
        
        print(f"✅ Login successful for {user.get('email')}")
        print(f"📧 User: {user.get('full_name')}")
        print(f"🔐 Password change required: {user.get('password_change_required', False)}")
        print(f"🎫 Access token received: {'Yes' if data.get('access_token') else 'No'}")
        
        access_token = data.get('access_token')
        return access_token, user.get('password_change_required', False)
    else:
        print(f"❌ Login failed: {response.text}")
        return None, False

def test_get_user_profile(access_token):
    """Test getting user profile to check password_change_required flag"""
    print("\n🔍 Testing User Profile Endpoint")
    print("=" * 40)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/me", headers=headers)
    
    if response.status_code == 200:
        user = response.json()
        print(f"✅ Profile retrieved for {user.get('email')}")
        print(f"🔐 Password change required: {user.get('password_change_required', False)}")
        return user.get('password_change_required', False)
    else:
        print(f"❌ Profile fetch failed: {response.text}")
        return False

def test_force_password_change(access_token):
    """Test forced password change for first-time login"""
    print("\n🔒 Testing Forced Password Change")
    print("=" * 40)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    password_data = {
        "new_password": "NewSecurePass123!",
        "confirm_password": "NewSecurePass123!"
    }
    
    response = requests.post(f"{BASE_URL}/force-change-password", 
                           json=password_data, headers=headers)
    
    if response.status_code == 200:
        print("✅ Password changed successfully!")
        return True
    else:
        print(f"❌ Password change failed: {response.text}")
        return False

def test_login_after_password_change():
    """Test login with new password"""
    print("\n🔓 Testing Login After Password Change")
    print("=" * 45)
    
    login_data = {
        "email": "kevin.mccullor@xylem.com",
        "password": "NewSecurePass123!"
    }
    
    response = requests.post(f"{BASE_URL}/login", json=login_data)
    
    if response.status_code == 200:
        data = response.json()
        user = data.get('user', {})
        
        print(f"✅ Login successful with new password")
        print(f"🔐 Password change required: {user.get('password_change_required', False)}")
        return not user.get('password_change_required', True)  # Should be False now
    else:
        print(f"❌ Login with new password failed: {response.text}")
        return False

def main():
    print("🔐 Password Change Requirements Test Suite")
    print("=" * 70)
    print()
    
    try:
        # Step 1: Login with user who needs password change
        access_token, needs_change = test_login_with_password_change_required()
        
        if not access_token:
            print("\n❌ Test failed: Could not login")
            return
        
        # Step 2: Verify profile shows password change required
        profile_needs_change = test_get_user_profile(access_token)
        
        if not profile_needs_change:
            print("\n⚠️  Warning: User doesn't need password change (test may be invalid)")
        
        # Step 3: Perform forced password change
        if profile_needs_change:
            change_success = test_force_password_change(access_token)
            
            if not change_success:
                print("\n❌ Test failed: Could not change password")
                return
        
        # Step 4: Test login with new password
        final_success = test_login_after_password_change()
        
        print("\n" + "=" * 70)
        if final_success:
            print("🎉 ALL TESTS PASSED!")
            print("✅ Password change requirement workflow is working correctly")
        else:
            print("❌ TESTS FAILED!")
            print("🔧 Password change requirement needs debugging")
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the reranker service is running on port 8008")
    except Exception as e:
        print(f"❌ Test Error: {e}")

if __name__ == "__main__":
    main()