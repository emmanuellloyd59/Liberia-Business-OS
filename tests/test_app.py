from app.models import User,BusinessApplication
from app.extensions import db
def register(client,email="owner@example.com"):
    return client.post("/auth/register",data={"full_name":"Test Owner","email":email,"password":"Strong-test-password-123"},follow_redirects=True)
def test_home_health(client):
    assert client.get("/").status_code==200
    response=client.get("/health")
    assert response.status_code==200 and response.json["status"]=="ok"
def test_registration_and_owner_application(client,app):
    response=register(client)
    assert response.status_code==200 and b"Your applications" in response.data
    response=client.post("/applications/new",data={"business_name":"Monrovia Test Traders","business_type":"Retail","county":"Montserrado","description":"Test application"},follow_redirects=True)
    assert response.status_code==200
    with app.app_context():
        user=User.query.filter_by(email="owner@example.com").one()
        item=BusinessApplication.query.filter_by(owner_id=user.id).one()
        assert item.status=="pending" and item.business_name=="Monrovia Test Traders"
def test_password_hashing(app):
    with app.app_context():
        user=User(email="hash@example.com",full_name="Hash Test"); user.set_password("another-strong-password")
        assert user.password_hash!="another-strong-password"
        assert user.check_password("another-strong-password")
        assert not user.check_password("wrong-password")
def test_non_admin_denied_admin_queue(client):
    register(client)
    assert client.get("/admin/applications").status_code==403
def test_directory_only_shows_approved(client,app):
    register(client)
    client.post("/applications/new",data={"business_name":"Pending Traders","business_type":"Retail","county":"Montserrado","description":"Not public yet"})
    response=client.get("/directory")
    assert b"Pending Traders" not in response.data
