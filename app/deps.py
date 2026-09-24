from fastapi import Header, HTTPException, Depends

def get_current_user_role(x_role: str = Header(...), x_user: str = Header(...)):
    valid_roles = ["Admin", "Accountant", "Student"]
    if x_role not in valid_roles:
        raise HTTPException(status_code=403, detail="Invalid role")
    return {"role": x_role, "user": x_user}

def require_admin(user: dict = Depends(get_current_user_role)):
    if user["role"] != "Admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user

def require_admin_or_accountant(user: dict = Depends(get_current_user_role)):
    if user["role"] not in ["Admin", "Accountant"]:
        raise HTTPException(status_code=403, detail="Elevated privileges required")
    return user