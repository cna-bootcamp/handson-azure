import requests
import concurrent.futures
import sys
import re
import json

def validate_email(email):
    """이메일 형식이 유효한지 검사"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email.strip()) is not None

def get_org_members_by_email(org_name, token):
    """조직의 모든 멤버와 이메일 정보 가져오기"""
    print(f"\n조직 '{org_name}'의 멤버 정보 가져오는 중...")
    
    url = f'https://api.github.com/orgs/{org_name}/members'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    members_map = {}
    try:
        # 모든 조직원 목록 가져오기
        all_members = []
        page = 1
        while True:
            response = requests.get(f"{url}?page={page}&per_page=100", headers=headers)
            response.raise_for_status()
            members = response.json()
            if not members:
                break
            all_members.extend(members)
            page += 1
        
        print(f"총 {len(all_members)}명의 조직원 정보 확인 중...")
        
        # 각 멤버의 이메일 정보 가져오기
        for i, member in enumerate(all_members):
            if i % 10 == 0 and i > 0:
                print(f"진행 중: {i}/{len(all_members)}...")
                
            username = member['login']
            members_map[username.lower()] = {
                'username': username,
                'email': None
            }
            
            # 사용자의 공개 이메일 정보 가져오기
            user_url = f"https://api.github.com/users/{username}"
            user_response = requests.get(user_url, headers=headers)
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                email = user_data.get('email')
                
                if email:
                    members_map[username.lower()]['email'] = email.lower()
        
        # 이메일 기반 맵 생성
        email_map = {}
        for username, data in members_map.items():
            if data['email']:
                email_map[data['email']] = data['username']
        
        print(f"이메일 정보가 있는 멤버: {len(email_map)}명")
        return email_map, [member for member in all_members]
    except Exception as e:
        print(f"멤버 정보 가져오기 실패: {e}")
        return {}, []

def get_team_id(org_name, team_slug, token):
    """팀 슬러그로 팀 ID 가져오기"""
    url = f'https://api.github.com/orgs/{org_name}/teams/{team_slug}'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        team_data = response.json()
        print(f"\n팀 정보:")
        print(f"팀 ID: {team_data['id']}")
        print(f"팀 이름: {team_data['name']}")
        return team_data['id']
    except requests.exceptions.RequestException as e:
        print(f"\n팀 정보 가져오기 실패: {e}")
        if hasattr(e, 'response') and e.response:
            try:
                print(f"오류 세부 내용: {json.dumps(e.response.json(), indent=2)}")
            except:
                print(f"응답: {e.response.text}")
        return None

def invite_by_email(org_name, team_slug, email, token, team_id, role='direct_member'):
    """이메일로 사용자를 GitHub 팀에 초대"""
    url = f'https://api.github.com/orgs/{org_name}/invitations'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    data = {
        'email': email.strip(),
        'role': role,
        'team_ids': [team_id]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        # 오류 체크 - 이미 멤버인지 확인
        if response.status_code == 422:
            try:
                error_data = response.json()
                errors = error_data.get('errors', [])
                for error in errors:
                    if error.get('message') == "A user with this email address is already a part of this organization":
                        return {"email": email, "result": "existing_member", "message": "이미 조직 멤버임"}
            except:
                pass
        
        response.raise_for_status()
        return {"email": email, "result": "invited", "message": "초대 성공"}
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                return {"email": email, "result": "error", "message": f"오류: {json.dumps(error_data)}"}
            except:
                return {"email": email, "result": "error", "message": f"오류: {e}"}
        else:
            return {"email": email, "result": "error", "message": f"오류: {e}"}

def main():
    token = input("GitHub 개인 액세스 토큰(admin:org 권한 필요): ").strip()
    org_name = input("GitHub 조직 이름: ").strip()
    team_slug = input("팀 슬러그(URL에 표시되는 팀 이름): ").strip()
    
    # 조직 멤버 정보 가져오기
    email_map, all_members = get_org_members_by_email(org_name, token)
    
    # 팀 ID 가져오기
    team_id = get_team_id(org_name, team_slug, token)
    if not team_id:
        print("팀 정보를 가져올 수 없습니다. 프로그램을 종료합니다.")
        sys.exit(1)
    
    # 이메일 목록 입력 받기
    print("\n쉼표로 구분된 이메일 목록을 입력하세요:")
    emails_input = input().strip()
    emails = [email.strip() for email in emails_input.split(',') if email.strip()]
    
    # 이메일 유효성 검사
    invalid_emails = [email for email in emails if not validate_email(email)]
    valid_emails = [email for email in emails if validate_email(email)]
    
    if invalid_emails:
        print(f"\n⚠️ 다음 이메일은 형식이 유효하지 않아 처리되지 않습니다:")
        for email in invalid_emails:
            print(f"  - {email}")
    
    if not valid_emails:
        print("유효한 이메일이 없습니다. 프로그램을 종료합니다.")
        sys.exit()
    
    # 이미 조직에 있는 멤버와 아닌 멤버 분류
    existing_members = []
    new_members = []
    
    for email in valid_emails:
        if email.lower() in email_map:
            existing_members.append({
                'email': email.lower(),
                'username': email_map[email.lower()]
            })
        else:
            new_members.append(email)
    
    # 확인 단계
    print(f"\n{org_name} 조직의 {team_slug} 팀에 초대할 이메일: {len(new_members)}개")
    
    # 새 멤버 초대
    if new_members:
        print(f"\n새 멤버 {len(new_members)}명을 초대합니다...")
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(invite_by_email, org_name, team_slug, email, token, team_id)
                for email in new_members
            ]
            
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # 결과 분류
        invited = []
        failed = []
        already_members = []
        
        for result in results:
            if result['result'] == 'invited':
                invited.append(result['email'])
            elif result['result'] == 'existing_member':
                already_members.append(result['email'])
                # 기존 멤버 목록에 추가
                found = False
                for member_email, username in email_map.items():
                    if member_email == result['email'].lower():
                        existing_members.append({
                            'email': result['email'],
                            'username': username
                        })
                        found = True
                        break
                
                # 사용자명을 찾지 못한 경우
                if not found:
                    existing_members.append({
                        'email': result['email'],
                        'username': None
                    })
            else:
                failed.append({
                    'email': result['email'],
                    'message': result['message']
                })
        
        # 결과 출력
        print("\n== 초대 결과 요약 ==")
        print(f"성공적으로 초대된 이메일: {len(invited)}개")
        
        if invited:
            print("\n성공적으로 초대된 이메일 목록:")
            for email in invited:
                print(f"  - {email}")
        
        print(f"\n이미 조직에 있는 것으로 확인된 이메일: {len(already_members)}개")
        
        if already_members:
            print("\n이미 조직에 있는 이메일 목록:")
            for email in already_members:
                print(f"  - {email}")
        
        print(f"\n초대 실패: {len(failed)}개")
        
        if failed:
            print("\n초대 실패한 이메일:")
            for item in failed:
                print(f"  - {item['email']}: {item['message']}")
    
    # 기존 멤버 안내
    if existing_members:
        print("\n== 이미 조직에 있는 멤버 목록 ==")
        print("다음 사용자는 이미 조직에 있으므로 수동으로 팀에 추가해야 합니다:")
        for member in existing_members:
            if 'username' in member and member['username']:
                print(f"  - {member['email']} (GitHub 사용자명: {member['username']})")
            else:
                print(f"  - {member['email']} (GitHub 사용자명을 찾을 수 없음)")
        
        print("\n== 팀에 수동으로 추가하는 방법 ==")
        print(f"1. GitHub 웹사이트에서 '{org_name}' 조직의 '{team_slug}' 팀 페이지로 이동합니다.")
        print("2. 'Add member' 버튼을 클릭합니다.")
        print("3. 위에 나열된 GitHub 사용자명을 입력하고 추가합니다.")

if __name__ == '__main__':
    main()

