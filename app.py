import os
import uuid
import shutil
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mysqldb import MySQL
import MySQLdb.cursors
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_PORT'] = 3306
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'password!!@@##$$'
app.config['MYSQL_DB'] = 'ged'

app.config['SECRET_KEY'] = '8f42a73d4f8854e3b8e142d9faa9f8c922fc62a1b4372c08'

mysql = MySQL(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

UPLOAD_FOLDER = r'DRIVE\uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'dwg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE Id = %s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    if user:
        return User(user['Id'], user['Username'], user['Role'])
    return None

@app.route('/')
@login_required
def home():
    return render_template('ged-main-page.html', user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE Username = %s', (username,))
        user = cursor.fetchone()
        cursor.close()
        
        if user and check_password_hash(user['Password'], password):
            user_obj = User(user['Id'], user['Username'], user['Role'])
            login_user(user_obj)
            flash('Logged in successfully.')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.')
    return render_template('ged-login-page.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/ld', methods=['GET'])
@login_required
def ld():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute('''
        SELECT p.ProjectCode 
        FROM ged.projects p
        JOIN ged.userprojects up ON p.Id = up.projectId
        WHERE up.userId = %s
        ORDER BY p.ProjectCode
    ''', (current_user.id,))
    
    projects = [row['ProjectCode'] for row in cursor.fetchall()]
    cursor.close()
    
    if not projects:
        flash('Você não está associado a nenhum projeto.', 'warning')
        return redirect(url_for('home'))
    
    return render_template('ld-main-page.html', 
                         columns=['Projeto', 'Documento', 'Data', 'Ações'] if current_user.role == 'planning' else ['Projeto', 'Documento', 'Data'],
                         dropdown_itens=projects,
                         user_role=current_user.role)

@app.route('/ld-selected', methods=['POST'])
@login_required
def ld_selected():
    selected_project = request.form.get('dropdown')

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute('''
        SELECT 1 FROM ged.userprojects up
        JOIN ged.projects p ON up.projectId = p.Id
        WHERE p.ProjectCode = %s AND up.userId = %s
    ''', (selected_project, current_user.id))
    
    if not cursor.fetchone():
        cursor.close()
        flash('Você não tem acesso a este projeto.', 'error')
        return redirect(url_for('ld'))

    cursor.execute('''
        SELECT p.ProjectCode 
        FROM ged.projects p
        JOIN ged.userprojects up ON p.Id = up.projectId
        WHERE up.userId = %s
        ORDER BY p.ProjectCode
    ''', (current_user.id,))
    
    projects = [row['ProjectCode'] for row in cursor.fetchall()]

    cursor.execute('SELECT Id FROM ged.projects WHERE ProjectCode = %s', (selected_project,))
    project = cursor.fetchone()
    project_id = project['Id'] if project else None

    cursor.execute('''
        SELECT dl.*, p.ProjectCode,
               CASE 
                   WHEN EXISTS (
                       SELECT 1 FROM ged.post post 
                       WHERE post.listId = dl.id 
                       AND post.rejectTimestamp IS NULL
                   ) THEN FALSE 
                   ELSE TRUE 
               END as can_modify
        FROM ged.documentlist dl
        JOIN ged.projects p ON dl.ProjectId = p.Id
        WHERE dl.ProjectId = %s
    ''', (project_id,))
    
    data = cursor.fetchall()
    cursor.close()

    formatted_data = []
    for row in data:
        if current_user.role == 'planning':
            formatted_data.append([
                row['ProjectCode'],
                row['DocumentCode'],
                row['DueDate'].strftime('%d/%m/%Y') if row['DueDate'] else '',
                {
                    'can_modify': row['can_modify'],
                    'id': row['id']
                }
            ])
        else:
            formatted_data.append([
                row['ProjectCode'],
                row['DocumentCode'],
                row['DueDate'].strftime('%d/%m/%Y') if row['DueDate'] else ''
            ])

    return render_template('ld-main-page.html', 
                         columns=['Projeto', 'Documento', 'Data', 'Ações'] if current_user.role == 'planning' else ['Projeto', 'Documento', 'Data'],
                         data=formatted_data, 
                         dropdown_itens=projects,
                         user_role=current_user.role,
                         selected_project=selected_project)

@app.route('/add-document', methods=['POST'])
@login_required
def add_document():
    if current_user.role != 'planning':
        return jsonify({'error': 'Unauthorized'}), 403

    project_code = request.form.get('projectCode')
    document_code = request.form.get('documentCode')
    due_date = request.form.get('dueDate')

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('SELECT Id FROM ged.projects WHERE ProjectCode = %s', (project_code,))
        project = cursor.fetchone()
        if not project:
            raise ValueError('Project not found')

        cursor.execute('''
            SELECT 1 FROM ged.documentlist 
            WHERE ProjectId = %s AND DocumentCode = %s
        ''', (project['Id'], document_code))
        if cursor.fetchone():
            raise ValueError('Document code already exists for this project')

        cursor.execute('''
            INSERT INTO ged.documentlist (ProjectId, DocumentCode, DueDate)
            VALUES (%s, %s, %s)
        ''', (project['Id'], document_code, due_date))

        mysql.connection.commit()
        cursor.close()
        flash('Documento adicionado com sucesso!', 'success')

    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        flash('Erro ao adicionar documento', 'error')

    return redirect(url_for('ld'))

@app.route('/edit-document/<int:doc_id>', methods=['POST'])
@login_required
def edit_document(doc_id):
    if current_user.role != 'planning':
        return jsonify({'error': 'Unauthorized'}), 403

    document_code = request.form.get('documentCode')
    due_date = request.form.get('dueDate')

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('''
            SELECT 1 FROM ged.post 
            WHERE listId = %s AND rejectTimestamp IS NOT NULL
        ''', (doc_id,))
        if cursor.fetchone():
            raise ValueError('Este documento não pode ser editado pois já possui postagens')

        cursor.execute('''
            SELECT ProjectId FROM ged.documentlist WHERE id = %s
        ''', (doc_id,))
        current_doc = cursor.fetchone()
        
        cursor.execute('''
            SELECT 1 FROM ged.documentlist 
            WHERE ProjectId = %s AND DocumentCode = %s AND id != %s
        ''', (current_doc['ProjectId'], document_code, doc_id))
        if cursor.fetchone():
            raise ValueError('Document code already exists for this project')

        cursor.execute('''
            UPDATE ged.documentlist 
            SET DocumentCode = %s, DueDate = %s
            WHERE id = %s
        ''', (document_code, due_date, doc_id))

        mysql.connection.commit()
        cursor.close()
        flash('Documento atualizado com sucesso!', 'success')

    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        flash('Erro ao atualizar documento', 'error')

    return redirect(url_for('ld'))

@app.route('/delete-document/<int:doc_id>', methods=['POST'])
@login_required
def delete_document(doc_id):
    if current_user.role != 'planning':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('''
            SELECT 1 FROM ged.post 
            WHERE listId = %s AND rejectTimestamp IS NULL
        ''', (doc_id,))
        if cursor.fetchone():
            raise ValueError('Este documento não pode ser excluído pois possui postagens ativas')

        cursor.execute('DELETE FROM ged.documentlist WHERE id = %s', (doc_id,))
        
        mysql.connection.commit()
        cursor.close()
        flash('Documento excluído com sucesso!', 'success')

    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        flash('Erro ao excluir documento', 'error')

    return redirect(url_for('ld'))

@app.route('/get-document/<int:doc_id>')
@login_required
def get_document(doc_id):
    if current_user.role != 'planning':
        return jsonify({'error': 'Unauthorized'}), 403

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM ged.documentlist WHERE id = %s', (doc_id,))
    doc = cursor.fetchone()
    cursor.close()

    if doc:
        return jsonify({
            'documentCode': doc['DocumentCode'],
            'dueDate': doc['DueDate'].strftime('%Y-%m-%d') if doc['DueDate'] else None
        })
    return jsonify({'error': 'Document not found'}), 404

@app.route('/post-document', methods=['GET', 'POST'])
@login_required
def post_document():
    if request.method == 'GET':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('''
            SELECT p.ProjectCode 
            FROM ged.projects p
            JOIN ged.userprojects up ON p.Id = up.projectId
            WHERE up.userId = %s
            ORDER BY p.ProjectCode
        ''', (current_user.id,))
        projects = cursor.fetchall()
        cursor.close()

        if not projects:
            flash('Você não está associado a nenhum projeto.', 'warning')
            return redirect(url_for('home'))

        return render_template('document-post-page.html', projects=projects)
    
    if request.method == 'POST':
        try:
            project_code = request.form['projectCode']
            document_code = request.form['documentCode']
            title = request.form['title']
            rev = request.form['rev']
            file = request.files['filename']

            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

            cursor.execute('''
                SELECT 1 FROM ged.userprojects up
                JOIN ged.projects p ON up.projectId = p.Id
                WHERE p.ProjectCode = %s AND up.userId = %s
            ''', (project_code, current_user.id))
            
            if not cursor.fetchone():
                cursor.close()
                flash('Você não tem acesso a este projeto.', 'error')
                return redirect(url_for('post_document'))

            if not file:
                flash('Nenhum arquivo selecionado', 'error')
                return redirect(url_for('post_document'))

            if not allowed_file(file.filename):
                flash('Tipo de arquivo não permitido', 'error')
                return redirect(url_for('post_document'))

            cursor.execute('''
                SELECT dl.id 
                FROM ged.documentlist dl
                JOIN ged.projects p ON dl.ProjectId = p.Id
                WHERE dl.DocumentCode = %s
                AND p.ProjectCode = %s
            ''', (document_code, project_code))
            
            document_list = cursor.fetchone()
            
            if not document_list:
                cursor.close()
                flash('Documento não encontrado', 'error')
                return redirect(url_for('post_document'))

            list_id = document_list['id']

            cursor.execute('''
                SELECT p.id, p.rejectTimestamp, i.id as issueId, r.id as returnId
                FROM ged.post p
                LEFT JOIN ged.issued i ON p.id = i.postId
                LEFT JOIN ged.return r ON i.id = r.IssueId
                WHERE p.listId = %s
                ORDER BY p.postTimestamp DESC
                LIMIT 1
            ''', (list_id,))
            
            last_post = cursor.fetchone()
            
            if last_post:
                if not last_post['rejectTimestamp']:
                    if not last_post['issueId']:
                        cursor.close()
                        flash('Não é possível postar nova revisão. A revisão anterior ainda está em análise.', 'warning')
                        return redirect(url_for('post_document'))
                    elif not last_post['returnId']:
                        cursor.close()
                        flash('Não é possível postar nova revisão. A revisão anterior ainda não recebeu retorno do cliente.', 'warning')
                        return redirect(url_for('post_document'))
            
            filename = secure_filename(file.filename)
            rand_id = str(uuid.uuid4())
            if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], rand_id)):
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], rand_id))
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], rand_id, filename)
            file.save(file_path)
            
            cursor.execute('''
                INSERT INTO ged.post 
                (listId, userId, rev, title, filename, folder)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (list_id, current_user.id, rev, title, filename, rand_id))
            
            mysql.connection.commit()
            cursor.close()
            
            flash('Documento postado com sucesso!', 'success')
            return redirect(url_for('my_posts'))
                
        except Exception as e:
            print(f"Error in post_document: {str(e)}")
            flash('Erro ao postar documento', 'error')
            return redirect(url_for('post_document'))

@app.route('/get-document-codes')
@login_required
def get_document_codes():
    project_code = request.args.get('projectCode')
    
    if not project_code:
        return jsonify({'documentCodes': []})
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = '''
            SELECT DISTINCT DocumentCode 
            FROM ged.full_documentlist 
            WHERE ProjectCode = %s
            ORDER BY DocumentCode
        '''
        cursor.execute(query, (project_code,))
        documents = cursor.fetchall()
        cursor.close()
        
        document_codes = [doc['DocumentCode'] for doc in documents]
        return jsonify({'documentCodes': document_codes})
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        return jsonify({'documentCodes': []}), 500

@app.route('/my-posts')
@login_required
def my_posts():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT 
            p.id,
            dl.DocumentCode,
            p.rev,
            p.title,
            p.postTimestamp,
            CASE 
                WHEN i.id IS NOT NULL THEN 'EMITIDO'
                ELSE 'EM ANÁLISE'
            END as status,
            p.folder,
            p.filename
        FROM ged.post p
        JOIN ged.documentlist dl ON p.listId = dl.id
        LEFT JOIN ged.issued i ON p.id = i.postId
        WHERE p.userId = %s
        ORDER BY p.postTimestamp DESC
    ''', (current_user.id,))
    
    posts = cursor.fetchall()
    cursor.close()
    
    return render_template('my-posts.html', posts=posts)

@app.route('/download/<folder>/<filename>')
@login_required
def download_file(folder, filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            flash('Arquivo não encontrado', 'error')
            return redirect(url_for('my_posts'))
    except Exception as e:
        flash('Erro ao baixar arquivo', 'error')
        return redirect(url_for('my_posts'))
    
@app.route('/approvals')
@login_required
def approvals():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        posts = []
        
        if current_user.role == 'manager':
            cursor.execute('''
                SELECT p.*, dl.DocumentCode, proj.ProjectCode, u.Username as postedBy 
                FROM ged.post p
                JOIN ged.documentlist dl ON p.listId = dl.id
                JOIN ged.projects proj ON dl.ProjectId = proj.Id
                JOIN ged.userprojects up ON proj.Id = up.projectId
                JOIN ged.users u ON p.userId = u.Id
                WHERE up.userId = %s
                AND p.managerApproval IS NULL
                ORDER BY p.postTimestamp DESC
            ''', (current_user.id,))
            posts = cursor.fetchall()
            
        elif current_user.role == 'archive':
            cursor.execute('''
                SELECT p.*, dl.DocumentCode, proj.ProjectCode, u.Username as postedBy 
                FROM ged.post p
                JOIN ged.documentlist dl ON p.listId = dl.id
                JOIN ged.projects proj ON dl.ProjectId = proj.Id
                JOIN ged.users u ON p.userId = u.Id
                WHERE p.managerApproval = TRUE 
                AND p.archiveApproval IS NULL
                ORDER BY p.postTimestamp DESC
            ''')
            posts = cursor.fetchall()
        
        cursor.close()
        return render_template('approvals.html', posts=posts, user_role=current_user.role)
        
    except Exception as e:
        print(f"Error in approvals route: {str(e)}")
        if 'cursor' in locals():
            cursor.close()
        flash('Erro ao carregar aprovações', 'error')
        return redirect(url_for('home'))

@app.route('/approve-post', methods=['POST'])
@login_required
def approve_post():
    post_id = request.form.get('post_id')
    approval_type = request.form.get('approval_type')
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        if approval_type == 'manager' and current_user.role == 'manager':
            cursor.execute('''
                UPDATE ged.post 
                SET managerApproval = TRUE, 
                    managerApprovalTimestamp = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (post_id,))
            
        elif approval_type == 'archive' and current_user.role == 'archive':
            cursor.execute('''
                SELECT p.*, dl.DocumentCode, proj.ProjectCode
                FROM ged.post p
                JOIN ged.documentlist dl ON p.listId = dl.id
                JOIN ged.projects proj ON dl.ProjectId = proj.Id
                WHERE p.id = %s
            ''', (post_id,))
            post_info = cursor.fetchone()

            cursor.execute('''
                UPDATE ged.post 
                SET archiveApproval = TRUE, 
                    archiveApprovalTimestamp = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (post_id,))
            
            cursor.execute('''
                INSERT INTO ged.issued (postId, issuedTimestamp)
                VALUES (%s, CURRENT_TIMESTAMP)
            ''', (post_id,))

            handle_issued_files(post_info['ProjectCode'], post_info['DocumentCode'], post_info, cursor)
            
        mysql.connection.commit()
        cursor.close()
        flash('Documento aprovado com sucesso!', 'success')
        
    except Exception as e:
        print(f"Error in approve_post: {str(e)}")
        if 'cursor' in locals():
            cursor.close()
        mysql.connection.rollback()
        flash('Erro ao aprovar documento', 'error')
        
    return redirect(url_for('approvals'))


def handle_issued_files(project_code, document_code, new_post, cursor):   
    
    issued_path = os.path.join('DRIVE', 'Issued', project_code)
    old_path = os.path.join(issued_path, 'old')
    
    os.makedirs(issued_path, exist_ok=True)
    os.makedirs(old_path, exist_ok=True)
    
    cursor.execute('''
        SELECT p.filename, p.folder, p.rev
        FROM ged.post p
        JOIN ged.issued i ON p.id = i.postId
        JOIN ged.documentlist dl ON p.listId = dl.id
        JOIN ged.projects proj ON dl.ProjectId = proj.Id
        WHERE proj.ProjectCode = %s
        AND dl.DocumentCode = %s
        AND p.id != %s
        ORDER BY i.issuedTimestamp DESC
        LIMIT 1
    ''', (project_code, document_code, new_post['id']))
    
    previous_issue = cursor.fetchone()
    
    if previous_issue:
        old_file_path = os.path.join('DRIVE', 'uploads', previous_issue['folder'], previous_issue['filename'])
        if os.path.exists(old_file_path):
            old_file_new_name = f"{document_code}_Rev_{previous_issue['rev']}{os.path.splitext(previous_issue['filename'])[1]}"
            old_file_dest = os.path.join(old_path, old_file_new_name)
            shutil.copy2(old_file_path, old_file_dest)

    new_file_path = os.path.join('DRIVE', 'uploads', new_post['folder'], new_post['filename'])
    if os.path.exists(new_file_path):
        new_file_new_name = f"{document_code}_Rev_{new_post['rev']}{os.path.splitext(new_post['filename'])[1]}"
        new_file_dest = os.path.join(issued_path, new_file_new_name)
        shutil.copy2(new_file_path, new_file_dest)

@app.route('/archive-area')
@login_required
def archive_area():
    if current_user.role != 'archive':
        flash('Acesso não autorizado', 'error')
        return redirect(url_for('home'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute('''
        SELECT i.id as issueId, p.id as postId, dl.DocumentCode, 
               proj.ProjectCode, p.rev, p.title, i.issuedTimestamp,
               u.Username as postedBy
        FROM ged.issued i
        JOIN ged.post p ON i.postId = p.id
        JOIN ged.documentlist dl ON p.listId = dl.id
        JOIN ged.projects proj ON dl.ProjectId = proj.Id
        JOIN ged.users u ON p.userId = u.Id
        LEFT JOIN ged.transmittal t ON i.id = t.IssueId
        WHERE t.Id IS NULL
        ORDER BY i.issuedTimestamp DESC
    ''')
    pending_transmittal = cursor.fetchall()
    
    cursor.execute('''
        SELECT i.id as issueId, p.id as postId, dl.DocumentCode, 
               proj.ProjectCode, p.rev, p.title, 
               t.TransmittalCode, t.TransmittalTimestamp,
               u.Username as postedBy
        FROM ged.issued i
        JOIN ged.post p ON i.postId = p.id
        JOIN ged.documentlist dl ON p.listId = dl.id
        JOIN ged.projects proj ON dl.ProjectId = proj.Id
        JOIN ged.users u ON p.userId = u.Id
        JOIN ged.transmittal t ON i.id = t.IssueId
        LEFT JOIN ged.return r ON i.id = r.IssueId
        WHERE r.Id IS NULL
        ORDER BY t.TransmittalTimestamp DESC
    ''')
    pending_return = cursor.fetchall()
    
    cursor.close()
    return render_template('archive-area.html', 
                         pending_transmittal=pending_transmittal,
                         pending_return=pending_return)

def get_next_code(project_code, code_type):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if code_type == 'T':
        table = 'transmittal_sequence'
    else:
        table = 'return_sequence'
    
    cursor.execute(f'''
        INSERT IGNORE INTO ged.{table} (ProjectCode, LastNumber)
        VALUES (%s, 0)
    ''', (project_code,))
    
    cursor.execute(f'''
        UPDATE ged.{table}
        SET LastNumber = LastNumber + 1
        WHERE ProjectCode = %s
    ''', (project_code,))
    
    cursor.execute(f'''
        SELECT LastNumber 
        FROM ged.{table}
        WHERE ProjectCode = %s
    ''', (project_code,))
    
    result = cursor.fetchone()
    number = result['LastNumber']
    
    mysql.connection.commit()
    cursor.close()
    
    return f"{project_code}-{code_type}-{str(number).zfill(4)}"

@app.route('/confirm-transmittal', methods=['POST'])
@login_required
def confirm_transmittal():
    if current_user.role != 'archive':
        return jsonify({'error': 'Unauthorized'}), 403
        
    issue_id = request.form.get('issueId')
    project_code = request.form.get('projectCode')
    
    try:
        transmittal_code = get_next_code(project_code, 'T')
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('''
            INSERT INTO ged.transmittal 
            (IssueId, TransmittalCode, TransmittalTimestamp)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
        ''', (issue_id, transmittal_code))
        
        mysql.connection.commit()
        cursor.close()
        flash('Transmittal confirmado com sucesso!', 'success')
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        mysql.connection.rollback()
        flash('Erro ao confirmar transmittal', 'error')
        
    return redirect(url_for('archive_area'))

@app.route('/confirm-return', methods=['POST'])
@login_required
def confirm_return():
    if current_user.role != 'archive':
        return jsonify({'error': 'Unauthorized'}), 403
        
    issue_id = request.form.get('issueId')
    project_code = request.form.get('projectCode')
    
    try:
        return_code = get_next_code(project_code, 'R')
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('''
            INSERT INTO ged.return 
            (IssueId, ReturnCode, ReturnTimestamp)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
        ''', (issue_id, return_code))
        
        mysql.connection.commit()
        cursor.close()
        flash('Retorno confirmado com sucesso!', 'success')
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        mysql.connection.rollback()
        flash('Erro ao confirmar retorno', 'error')
        
    return redirect(url_for('archive_area'))

@app.route('/manager-area')
@login_required
def manager_area():
    if current_user.role != 'manager':
        flash('Acesso não autorizado', 'error')
        return redirect(url_for('home'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute('''
        SELECT p.* 
        FROM ged.projects p
        JOIN ged.userprojects up ON p.Id = up.projectId
        WHERE up.userId = %s
        ORDER BY p.ProjectCode
    ''', (current_user.id,))
    projects = cursor.fetchall()
    
    cursor.execute('SELECT Id, Username, Role FROM ged.users ORDER BY Username')
    users = cursor.fetchall()
    
    project_teams = {}
    for project in projects:
        cursor.execute('''
            SELECT u.Id, u.Username, u.Role 
            FROM ged.users u
            JOIN ged.userprojects up ON u.Id = up.userId
            WHERE up.projectId = %s
            ORDER BY u.Username
        ''', (project['Id'],))
        project_teams[project['Id']] = cursor.fetchall()
    
    cursor.close()
    return render_template('manager-area.html', 
                         projects=projects,
                         users=users,
                         project_teams=project_teams)

@app.route('/add-project-user', methods=['POST'])
@login_required
def add_project_user():
    if current_user.role != 'manager':
        return jsonify({'error': 'Unauthorized'}), 403
        
    project_id = request.form.get('projectId')
    user_id = request.form.get('userId')
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('''
            SELECT 1 FROM ged.userprojects 
            WHERE projectId = %s AND userId = %s
        ''', (project_id, current_user.id))
        
        if not cursor.fetchone():
            cursor.close()
            flash('Acesso não autorizado ao projeto', 'error')
            return redirect(url_for('manager_area'))
            
        cursor.execute('''
            SELECT 1 FROM ged.userprojects 
            WHERE projectId = %s AND userId = %s
        ''', (project_id, user_id))
        
        if cursor.fetchone():
            cursor.close()
            flash('Usuário já está no projeto', 'warning')
            return redirect(url_for('manager_area'))
        
        cursor.execute('''
            INSERT INTO ged.userprojects (projectId, userId)
            VALUES (%s, %s)
        ''', (project_id, user_id))
        
        mysql.connection.commit()
        cursor.close()
        flash('Usuário adicionado com sucesso!', 'success')
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        mysql.connection.rollback()
        flash('Erro ao adicionar usuário', 'error')
        
    return redirect(url_for('manager_area'))

@app.route('/remove-project-user', methods=['POST'])
@login_required
def remove_project_user():
    if current_user.role != 'manager':
        return jsonify({'error': 'Unauthorized'}), 403
        
    project_id = request.form.get('projectId')
    user_id = request.form.get('userId')
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('''
            SELECT 1 FROM ged.userprojects 
            WHERE projectId = %s AND userId = %s
        ''', (project_id, current_user.id))
        
        if not cursor.fetchone():
            cursor.close()
            flash('Acesso não autorizado ao projeto', 'error')
            return redirect(url_for('manager_area'))
        
        cursor.execute('''
            SELECT COUNT(*) as manager_count 
            FROM ged.userprojects up
            JOIN ged.users u ON up.userId = u.Id
            WHERE up.projectId = %s AND u.Role = 'manager'
        ''', (project_id,))
        
        manager_count = cursor.fetchone()['manager_count']
        
        cursor.execute('SELECT Role FROM ged.users WHERE Id = %s', (user_id,))
        user_role = cursor.fetchone()['Role']
        
        if manager_count <= 1 and user_role == 'manager':
            cursor.close()
            flash('Não é possível remover o último gerente do projeto', 'error')
            return redirect(url_for('manager_area'))
        
        cursor.execute('''
            DELETE FROM ged.userprojects 
            WHERE projectId = %s AND userId = %s
        ''', (project_id, user_id))
        
        mysql.connection.commit()
        cursor.close()
        flash('Usuário removido com sucesso!', 'success')
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        mysql.connection.rollback()
        flash('Erro ao remover usuário', 'error')
        
    return redirect(url_for('manager_area'))

@app.route('/admin-area')
@login_required
def admin_area():
    if current_user.role != 'admin':
        flash('Acesso não autorizado', 'error')
        return redirect(url_for('home'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM ged.users ORDER BY Username')
    users = cursor.fetchall()
    
    cursor.execute('SELECT * FROM ged.projects ORDER BY ProjectCode')
    projects = cursor.fetchall()
    cursor.close()
    
    roles = {
        'admin': 'Administrador',
        'manager': 'Gerente',
        'archive': 'Arquivo',
        'planning': 'Planejamento',
        'engineering': 'Engenharia'
    }
    
    project_statuses = {
        'STARTING': 'Iniciando',
        'IN_PROGRESS': 'Em Andamento',
        'ON_HOLD': 'Em Espera',
        'COMPLETED': 'Concluído',
        'CANCELLED': 'Cancelado'
    }
    
    return render_template('admin-area.html', 
                         users=users, 
                         roles=roles,
                         projects=projects,
                         project_statuses=project_statuses)

@app.route('/add-user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    username = request.form.get('username')
    role = request.form.get('role')
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('SELECT 1 FROM ged.users WHERE Username = %s', (username,))
        if cursor.fetchone():
            flash('Nome de usuário já existe', 'error')
            return redirect(url_for('admin_area'))
        
        cursor.execute('''
            INSERT INTO ged.users (Username, Password, Role)
            VALUES (%s, NULL, %s)
        ''', (username, role))
        
        mysql.connection.commit()
        cursor.close()
        flash('Usuário adicionado com sucesso!', 'success')
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        mysql.connection.rollback()
        flash('Erro ao adicionar usuário', 'error')
        
    return redirect(url_for('admin_area'))

@app.route('/add-project', methods=['POST'])
@login_required
def add_project():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    project_code = request.form.get('projectCode')
    project_name = request.form.get('projectName')
    client_name = request.form.get('clientName')
    start_date = request.form.get('startDate')
    end_date = request.form.get('endDate') or None
    project_status = request.form.get('projectStatus')
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('SELECT 1 FROM ged.projects WHERE ProjectCode = %s', (project_code,))
        if cursor.fetchone():
            flash('Código de projeto já existe', 'error')
            return redirect(url_for('admin_area'))
        
        cursor.execute('''
            INSERT INTO ged.projects 
            (ProjectCode, ProjectName, ClientName, StartDate, EndDate, ProjectStatus)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (project_code, project_name, client_name, start_date, end_date, project_status))
        
        mysql.connection.commit()
        cursor.close()
        flash('Projeto adicionado com sucesso!', 'success')
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        mysql.connection.rollback()
        flash('Erro ao adicionar projeto', 'error')
        
    return redirect(url_for('admin_area'))

@app.route('/get-project/<int:project_id>')
@login_required
def get_project(project_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT Id, ProjectCode, ProjectName, ClientName, 
               DATE_FORMAT(StartDate, '%%Y-%%m-%%d') as StartDate,
               DATE_FORMAT(EndDate, '%%Y-%%m-%%d') as EndDate,
               ProjectStatus
        FROM ged.projects WHERE Id = %s
    ''', (project_id,))
    project = cursor.fetchone()
    cursor.close()

    if project:
        return jsonify(project)
    return jsonify({'error': 'Project not found'}), 404

@app.route('/edit-project/<int:project_id>', methods=['POST'])
@login_required
def edit_project(project_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    project_code = request.form.get('projectCode')
    project_name = request.form.get('projectName')
    client_name = request.form.get('clientName')
    start_date = request.form.get('startDate')
    end_date = request.form.get('endDate') or None
    project_status = request.form.get('projectStatus')
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('''
            SELECT 1 FROM ged.projects 
            WHERE ProjectCode = %s AND Id != %s
        ''', (project_code, project_id))
        if cursor.fetchone():
            flash('Código de projeto já existe', 'error')
            return redirect(url_for('admin_area'))
        
        cursor.execute('''
            UPDATE ged.projects 
            SET ProjectCode = %s,
                ProjectName = %s,
                ClientName = %s,
                StartDate = %s,
                EndDate = %s,
                ProjectStatus = %s
            WHERE Id = %s
        ''', (project_code, project_name, client_name, start_date, end_date, 
              project_status, project_id))
        
        mysql.connection.commit()
        cursor.close()
        flash('Projeto atualizado com sucesso!', 'success')
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        mysql.connection.rollback()
        flash('Erro ao atualizar projeto', 'error')
        
    return redirect(url_for('admin_area'))

@app.route('/delete-project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('''
            SELECT 1 FROM ged.documentlist 
            WHERE ProjectId = %s
        ''', (project_id,))
        
        if cursor.fetchone():
            flash('Não é possível excluir o projeto pois existem documentos associados', 'error')
            return redirect(url_for('admin_area'))
        
        cursor.execute('DELETE FROM ged.projects WHERE Id = %s', (project_id,))
        
        mysql.connection.commit()
        cursor.close()
        flash('Projeto excluído com sucesso!', 'success')
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        mysql.connection.rollback()
        flash('Erro ao excluir projeto', 'error')
        
    return redirect(url_for('admin_area'))

@app.route('/set-initial-password', methods=['POST'])
def set_initial_password():
    username = request.form.get('username')
    password = request.form.get('password')
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('''
            SELECT * FROM ged.users 
            WHERE Username = %s AND Password IS NULL
        ''', (username,))
        
        user = cursor.fetchone()
        if not user:
            flash('Usuário não encontrado ou senha já definida', 'error')
            return redirect(url_for('login'))
        
        hashed_password = generate_password_hash(password)
        cursor.execute('''
            UPDATE ged.users 
            SET Password = %s 
            WHERE Username = %s AND Password IS NULL
        ''', (hashed_password, username))
        
        mysql.connection.commit()
        cursor.close()
        flash('Senha definida com sucesso! Faça login para continuar.', 'success')
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        mysql.connection.rollback()
        flash('Erro ao definir senha', 'error')
        
    return redirect(url_for('login'))

@app.route('/all-issues')
@login_required
def all_issues():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute('''
        SELECT 
            p.ProjectCode,
            dl.DocumentCode,
            post.rev,
            post.title,
            i.issuedTimestamp,
            t.TransmittalCode,
            t.TransmittalTimestamp,
            r.ReturnCode,
            r.ReturnTimestamp,
            u.Username as postedBy
        FROM ged.issued i
        JOIN ged.post post ON i.postId = post.id
        JOIN ged.documentlist dl ON post.listId = dl.id
        JOIN ged.projects p ON dl.ProjectId = p.Id
        JOIN ged.users u ON post.userId = u.Id
        JOIN ged.userprojects up ON p.Id = up.projectId
        LEFT JOIN ged.transmittal t ON i.id = t.IssueId
        LEFT JOIN ged.return r ON i.id = r.IssueId
        WHERE up.userId = %s
        ORDER BY i.issuedTimestamp DESC
    ''', (current_user.id,))
    
    issues = cursor.fetchall()
    cursor.close()

    if not issues:
        flash('Não há emissões nos seus projetos.', 'info')
    
    return render_template('all-issues.html', issues=issues)

if __name__ == '__main__':
    app.run(debug=True, port = '8080')
    