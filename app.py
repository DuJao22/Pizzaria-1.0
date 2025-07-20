from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import hashlib
import os
from datetime import datetime
import urllib.parse
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io
import base64

app = Flask(__name__)
app.secret_key = 'pizzaria_secret_key_2024'

# Configuração do banco de dados
def init_db():
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Tabela de usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'garcom',
            ativo INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de categorias
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    # Tabela de produtos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT,
            categoria_id INTEGER,
            preco_p REAL,
            preco_m REAL,
            preco_g REAL,
            preco_familia REAL,
            foto TEXT,
            ativo INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (categoria_id) REFERENCES categorias (id)
        )
    ''')
    
    # Tabela de mesas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mesas (
            id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'livre',
            pedido_aberto INTEGER DEFAULT 0,
            total REAL DEFAULT 0.0,
            opened_at TIMESTAMP,
            closed_at TIMESTAMP
        )
    ''')
    
    # Tabela de pedidos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mesa_id INTEGER,
            tipo TEXT NOT NULL,
            status TEXT DEFAULT 'aberto',
            total REAL DEFAULT 0.0,
            usuario_id INTEGER,
            cliente_nome TEXT,
            cliente_telefone TEXT,
            observacoes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            FOREIGN KEY (mesa_id) REFERENCES mesas (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabela de itens do pedido
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itens_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER,
            produto_id INTEGER,
            produto_nome TEXT,
            tamanho TEXT,
            quantidade INTEGER DEFAULT 1,
            preco_unitario REAL,
            subtotal REAL,
            sabor2_id INTEGER,
            sabor2_nome TEXT,
            observacoes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pedido_id) REFERENCES pedidos (id),
            FOREIGN KEY (produto_id) REFERENCES produtos (id)
        )
    ''')
    
    # Tabela de configurações
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY,
            nome_sistema TEXT DEFAULT 'PizzaSystem',
            logo_sistema TEXT,
            telefone_whatsapp TEXT DEFAULT '5511999999999',
            endereco TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Inserir dados iniciais
    # Usuário admin padrão
    admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, password, tipo) 
        VALUES (?, ?, ?)
    ''', ('admin', admin_password, 'admin'))
    
    # Usuário garçom padrão
    garcom_password = hashlib.sha256('garcom123'.encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, password, tipo) 
        VALUES (?, ?, ?)
    ''', ('garcom', garcom_password, 'garcom'))
    
    # Configurações padrão
    cursor.execute('''
        INSERT OR IGNORE INTO configuracoes (id, nome_sistema) 
        VALUES (1, 'PizzaSystem')
    ''')
    
    # Categorias padrão
    categorias = ['Pizzas', 'Refrigerantes', 'Adicionais']
    for categoria in categorias:
        cursor.execute('INSERT OR IGNORE INTO categorias (nome) VALUES (?)', (categoria,))
    
    # Mesas (1 a 10)
    for i in range(1, 11):
        cursor.execute('INSERT OR IGNORE INTO mesas (id) VALUES (?)', (i,))
    
    # Produtos exemplo
    pizzas = [
        ('Margherita', 'Molho de tomate, mussarela, manjericão', 25.00, 35.00, 45.00, 55.00),
        ('Calabresa', 'Molho de tomate, mussarela, calabresa, cebola', 28.00, 38.00, 48.00, 58.00),
        ('Portuguesa', 'Molho de tomate, mussarela, presunto, ovos, cebola, azeitona', 30.00, 40.00, 50.00, 60.00),
        ('Frango com Catupiry', 'Molho de tomate, mussarela, frango desfiado, catupiry', 32.00, 42.00, 52.00, 62.00)
    ]
    
    for pizza in pizzas:
        cursor.execute('''
            INSERT OR IGNORE INTO produtos (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia)
            VALUES (?, ?, 1, ?, ?, ?, ?)
        ''', pizza)
    
    # Refrigerantes
    refrigerantes = [
        ('Coca-Cola 350ml', 'Refrigerante Coca-Cola lata 350ml', 5.00),
        ('Guaraná 350ml', 'Refrigerante Guaraná lata 350ml', 5.00),
        ('Fanta Laranja 350ml', 'Refrigerante Fanta Laranja lata 350ml', 5.00)
    ]
    
    for refri in refrigerantes:
        cursor.execute('''
            INSERT OR IGNORE INTO produtos (nome, descricao, categoria_id, preco_p)
            VALUES (?, ?, 2, ?)
        ''', refri)
    
    conn.commit()
    conn.close()

# Função para verificar login
def verificar_login():
    if 'user_id' not in session:
        return False
    return True

def verificar_admin():
    if not verificar_login() or session.get('user_tipo') != 'admin':
        return False
    return True

def verificar_garcom_ou_admin():
    if not verificar_login():
        return False
    return session.get('user_tipo') in ['admin', 'garcom']

def get_configuracoes():
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('SELECT nome_sistema, logo_sistema, telefone_whatsapp FROM configuracoes WHERE id = 1')
    config = cursor.fetchone()
    conn.close()
    if config:
        return {
            'nome_sistema': config[0],
            'logo_sistema': config[1],
            'telefone_whatsapp': config[2]
        }
    return {
        'nome_sistema': 'PizzaSystem',
        'logo_sistema': None,
        'telefone_whatsapp': '5511999999999'
    }

# Rota principal
@app.route('/')
def index():
    if verificar_login():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    config = get_configuracoes()
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        conn = sqlite3.connect('pizzaria.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, tipo FROM usuarios WHERE username = ? AND password = ? AND ativo = 1', 
                      (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['user_tipo'] = user[2]
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha incorretos!', 'error')
    
    return render_template('login.html', config=config)

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('login'))

# Dashboard
@app.route('/dashboard')
def dashboard():
    if not verificar_login():
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Estatísticas do dia
    hoje = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM pedidos WHERE DATE(created_at) = ? AND status = "fechado"', (hoje,))
    pedidos_hoje = cursor.fetchone()[0]
    
    cursor.execute('SELECT COALESCE(SUM(total), 0) FROM pedidos WHERE DATE(created_at) = ? AND status = "fechado"', (hoje,))
    vendas_hoje = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM mesas WHERE status = "ocupada"')
    mesas_ocupadas = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM produtos WHERE ativo = 1')
    total_produtos = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template('dashboard.html',
                         config=config,
                         pedidos_hoje=pedidos_hoje,
                         vendas_hoje=vendas_hoje,
                         mesas_ocupadas=mesas_ocupadas,
                         total_produtos=total_produtos)

# Configurações
@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    config = get_configuracoes()
    
    if request.method == 'POST':
        nome_sistema = request.form['nome_sistema']
        telefone_whatsapp = request.form['telefone_whatsapp']
        endereco = request.form.get('endereco', '')
        
        conn = sqlite3.connect('pizzaria.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE configuracoes 
            SET nome_sistema = ?, telefone_whatsapp = ?, endereco = ?, updated_at = ?
            WHERE id = 1
        ''', (nome_sistema, telefone_whatsapp, endereco, datetime.now()))
        conn.commit()
        conn.close()
        
        flash('Configurações atualizadas com sucesso!', 'success')
        return redirect(url_for('configuracoes'))
    
    return render_template('configuracoes.html', config=config)

# Produtos
@app.route('/produtos')
def produtos():
    if not verificar_login():
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.nome, p.descricao, c.nome as categoria, 
               p.preco_p, p.preco_m, p.preco_g, p.preco_familia, p.ativo
        FROM produtos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        ORDER BY c.nome, p.nome
    ''')
    produtos = cursor.fetchall()
    
    cursor.execute('SELECT id, nome FROM categorias WHERE ativo = 1')
    categorias = cursor.fetchall()
    
    conn.close()
    
    return render_template('produtos.html', produtos=produtos, categorias=categorias, config=config)

@app.route('/produtos/adicionar', methods=['POST'])
def adicionar_produto():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('produtos'))
    
    nome = request.form['nome']
    descricao = request.form['descricao']
    categoria_id = request.form['categoria_id']
    preco_p = request.form.get('preco_p', 0) or 0
    preco_m = request.form.get('preco_m', 0) or 0
    preco_g = request.form.get('preco_g', 0) or 0
    preco_familia = request.form.get('preco_familia', 0) or 0
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO produtos (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia))
    conn.commit()
    conn.close()
    
    flash('Produto adicionado com sucesso!', 'success')
    return redirect(url_for('produtos'))

@app.route('/produtos/editar/<int:produto_id>', methods=['GET', 'POST'])
def editar_produto(produto_id):
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('produtos'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        descricao = request.form['descricao']
        categoria_id = request.form['categoria_id']
        preco_p = request.form.get('preco_p', 0) or 0
        preco_m = request.form.get('preco_m', 0) or 0
        preco_g = request.form.get('preco_g', 0) or 0
        preco_familia = request.form.get('preco_familia', 0) or 0
        
        cursor.execute('''
            UPDATE produtos 
            SET nome = ?, descricao = ?, categoria_id = ?, preco_p = ?, preco_m = ?, preco_g = ?, preco_familia = ?
            WHERE id = ?
        ''', (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia, produto_id))
        conn.commit()
        conn.close()
        
        flash('Produto atualizado com sucesso!', 'success')
        return redirect(url_for('produtos'))
    
    # GET - buscar produto para edição
    cursor.execute('''
        SELECT p.id, p.nome, p.descricao, p.categoria_id, c.nome as categoria,
               p.preco_p, p.preco_m, p.preco_g, p.preco_familia, p.ativo
        FROM produtos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.id = ?
    ''', (produto_id,))
    produto = cursor.fetchone()
    
    cursor.execute('SELECT id, nome FROM categorias WHERE ativo = 1')
    categorias = cursor.fetchall()
    
    conn.close()
    
    if not produto:
        flash('Produto não encontrado!', 'error')
        return redirect(url_for('produtos'))
    
    return render_template('editar_produto.html', produto=produto, categorias=categorias, config=config)

@app.route('/produtos/toggle/<int:produto_id>')
def toggle_produto(produto_id):
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('produtos'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE produtos SET ativo = NOT ativo WHERE id = ?', (produto_id,))
    conn.commit()
    conn.close()
    
    flash('Status do produto alterado!', 'success')
    return redirect(url_for('produtos'))

# Mesas
@app.route('/mesas')
def mesas():
    if not verificar_login():
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.id, m.status, m.total, 
               CASE WHEN p.id IS NOT NULL THEN p.id ELSE 0 END as pedido_id
        FROM mesas m
        LEFT JOIN pedidos p ON m.id = p.mesa_id AND p.status = 'aberto'
        ORDER BY m.id
    ''')
    mesas = cursor.fetchall()
    conn.close()
    
    return render_template('mesas.html', mesas=mesas, config=config)

@app.route('/mesa/<int:mesa_id>/abrir')
def abrir_mesa(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Verificar se mesa já está ocupada
    cursor.execute('SELECT status FROM mesas WHERE id = ?', (mesa_id,))
    mesa = cursor.fetchone()
    
    if mesa and mesa[0] == 'livre':
        # Abrir mesa
        cursor.execute('UPDATE mesas SET status = "ocupada", opened_at = ? WHERE id = ?', 
                      (datetime.now(), mesa_id))
        
        # Criar pedido
        cursor.execute('''
            INSERT INTO pedidos (mesa_id, tipo, usuario_id) 
            VALUES (?, ?, ?)
        ''', (mesa_id, 'salao', session['user_id']))
        
        conn.commit()
        flash(f'Mesa {mesa_id} aberta com sucesso!', 'success')
    else:
        flash(f'Mesa {mesa_id} já está ocupada!', 'error')
    
    conn.close()
    return redirect(url_for('mesas'))

# Pedidos
@app.route('/pedido/<int:mesa_id>')
def pedido_mesa(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar pedido aberto da mesa
    cursor.execute('SELECT id, total FROM pedidos WHERE mesa_id = ? AND status = "aberto"', (mesa_id,))
    pedido = cursor.fetchone()
    
    if not pedido:
        flash('Mesa não possui pedido aberto!', 'error')
        return redirect(url_for('mesas'))
    
    # Buscar produtos para o cardápio
    cursor.execute('''
        SELECT p.id, p.nome, p.descricao, c.nome as categoria,
               p.preco_p, p.preco_m, p.preco_g, p.preco_familia
        FROM produtos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.ativo = 1
        ORDER BY c.nome, p.nome
    ''')
    produtos = cursor.fetchall()
    
    # Buscar itens do pedido
    cursor.execute('''
        SELECT ip.id, ip.produto_nome, ip.tamanho, ip.quantidade, 
               ip.preco_unitario, ip.subtotal, ip.sabor2_nome
        FROM itens_pedido ip
        WHERE ip.pedido_id = ?
        ORDER BY ip.created_at
    ''', (pedido[0],))
    itens = cursor.fetchall()
    
    conn.close()
    
    return render_template('pedido.html', mesa_id=mesa_id, pedido=pedido, produtos=produtos, itens=itens, config=config)

@app.route('/pedido/<int:mesa_id>/adicionar_item', methods=['POST'])
def adicionar_item_pedido(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    produto_id = request.form['produto_id']
    tamanho = request.form['tamanho']
    quantidade = int(request.form['quantidade'])
    sabor2_id = request.form.get('sabor2_id')
    observacoes = request.form.get('observacoes', '')
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar pedido
    cursor.execute('SELECT id FROM pedidos WHERE mesa_id = ? AND status = "aberto"', (mesa_id,))
    pedido = cursor.fetchone()
    
    if not pedido:
        flash('Pedido não encontrado!', 'error')
        return redirect(url_for('mesas'))
    
    # Buscar produto principal
    cursor.execute('SELECT nome, preco_p, preco_m, preco_g, preco_familia FROM produtos WHERE id = ?', (produto_id,))
    produto = cursor.fetchone()
    
    # Determinar preço baseado no tamanho
    precos = {'P': produto[1], 'M': produto[2], 'G': produto[3], 'Família': produto[4]}
    preco_base = precos.get(tamanho, produto[1])
    
    # Se for pizza meio a meio, calcular pela mais cara
    sabor2_nome = None
    if sabor2_id:
        cursor.execute('SELECT nome, preco_p, preco_m, preco_g, preco_familia FROM produtos WHERE id = ?', (sabor2_id,))
        sabor2 = cursor.fetchone()
        sabor2_nome = sabor2[0]
        preco_sabor2 = precos.get(tamanho, sabor2[1])
        preco_base = max(preco_base, preco_sabor2)
    
    preco_unitario = preco_base
    subtotal = preco_unitario * quantidade
    
    # Adicionar item ao pedido
    cursor.execute('''
        INSERT INTO itens_pedido (pedido_id, produto_id, produto_nome, tamanho, quantidade, 
                                 preco_unitario, subtotal, sabor2_id, sabor2_nome, observacoes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (pedido[0], produto_id, produto[0], tamanho, quantidade, preco_unitario, subtotal, 
          sabor2_id, sabor2_nome, observacoes))
    
    # Atualizar total do pedido
    cursor.execute('SELECT SUM(subtotal) FROM itens_pedido WHERE pedido_id = ?', (pedido[0],))
    total = cursor.fetchone()[0] or 0
    
    cursor.execute('UPDATE pedidos SET total = ? WHERE id = ?', (total, pedido[0]))
    cursor.execute('UPDATE mesas SET total = ? WHERE id = ?', (total, mesa_id))
    
    conn.commit()
    conn.close()
    
    flash('Item adicionado ao pedido!', 'success')
    return redirect(url_for('pedido_mesa', mesa_id=mesa_id))

def gerar_pdf_mesa(mesa_id):
    """Gera PDF com resumo da mesa para fechamento de caixa"""
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar dados da mesa e pedido
    cursor.execute('SELECT id, total, created_at FROM pedidos WHERE mesa_id = ? AND status = "aberto"', (mesa_id,))
    pedido = cursor.fetchone()
    
    if not pedido:
        return None
    
    cursor.execute('''
        SELECT produto_nome, tamanho, quantidade, preco_unitario, subtotal, sabor2_nome, observacoes
        FROM itens_pedido
        WHERE pedido_id = ?
        ORDER BY created_at
    ''', (pedido[0],))
    itens = cursor.fetchall()
    
    conn.close()
    
    # Criar PDF em memória
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center
    )
    story.append(Paragraph(f"{config['nome_sistema']}", title_style))
    story.append(Paragraph(f"FECHAMENTO DE CAIXA - MESA {mesa_id}", title_style))
    story.append(Spacer(1, 20))
    
    # Informações do pedido
    info_data = [
        ['Pedido:', f"#{pedido[0]}"],
        ['Mesa:', f"{mesa_id}"],
        ['Data/Hora:', datetime.now().strftime('%d/%m/%Y %H:%M:%S')],
        ['Atendente:', session.get('username', 'N/A')]
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Tabela de itens
    if itens:
        story.append(Paragraph("ITENS CONSUMIDOS", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        # Cabeçalho da tabela
        data = [['Item', 'Tamanho', 'Qtd', 'Valor Unit.', 'Subtotal']]
        
        # Adicionar itens
        for item in itens:
            nome_completo = item[0]
            if item[5]:  # sabor2_nome
                nome_completo += f" + {item[5]}"
            
            data.append([
                nome_completo,
                item[1],  # tamanho
                str(item[2]),  # quantidade
                f"R$ {item[3]:.2f}",  # preco_unitario
                f"R$ {item[4]:.2f}"   # subtotal
            ])
        
        # Linha de total
        data.append(['', '', '', 'TOTAL:', f"R$ {pedido[1]:.2f}"])
        
        table = Table(data, colWidths=[3*inch, 1*inch, 0.7*inch, 1*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgreen),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(table)
    
    story.append(Spacer(1, 30))
    story.append(Paragraph("_" * 50, styles['Normal']))
    story.append(Paragraph("Assinatura do Cliente", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/mesa/<int:mesa_id>/fechar')
def fechar_mesa(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar pedido e itens
    cursor.execute('SELECT id, total FROM pedidos WHERE mesa_id = ? AND status = "aberto"', (mesa_id,))
    pedido = cursor.fetchone()
    
    if not pedido:
        flash('Mesa não possui pedido aberto!', 'error')
        return redirect(url_for('mesas'))
    
    cursor.execute('''
        SELECT produto_nome, tamanho, quantidade, preco_unitario, subtotal, sabor2_nome
        FROM itens_pedido
        WHERE pedido_id = ?
        ORDER BY created_at
    ''', (pedido[0],))
    itens = cursor.fetchall()
    
    conn.close()
    
    return render_template('fechar_mesa.html', mesa_id=mesa_id, pedido=pedido, itens=itens, config=config)

@app.route('/mesa/<int:mesa_id>/pdf')
def gerar_pdf_fechamento(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    pdf_buffer = gerar_pdf_mesa(mesa_id)
    if not pdf_buffer:
        flash('Mesa não possui pedido aberto!', 'error')
        return redirect(url_for('mesas'))
    
    from flask import Response
    return Response(
        pdf_buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=fechamento_mesa_{mesa_id}.pdf'}
    )

@app.route('/mesa/<int:mesa_id>/finalizar', methods=['POST'])
def finalizar_mesa(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Fechar pedido
    cursor.execute('''
        UPDATE pedidos SET status = "fechado", closed_at = ?
        WHERE mesa_id = ? AND status = "aberto"
    ''', (datetime.now(), mesa_id))
    
    # Liberar mesa
    cursor.execute('''
        UPDATE mesas SET status = "livre", total = 0, closed_at = ?
        WHERE id = ?
    ''', (datetime.now(), mesa_id))
    
    conn.commit()
    conn.close()
    
    flash(f'Mesa {mesa_id} fechada com sucesso!', 'success')
    return redirect(url_for('mesas'))

# Retirada
@app.route('/retirada')
def retirada():
    if not verificar_login():
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar produtos para o cardápio
    cursor.execute('''
        SELECT p.id, p.nome, p.descricao, c.nome as categoria,
               p.preco_p, p.preco_m, p.preco_g, p.preco_familia
        FROM produtos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.ativo = 1
        ORDER BY c.nome, p.nome
    ''')
    produtos = cursor.fetchall()
    
    conn.close()
    
    return render_template('retirada.html', produtos=produtos, config=config)

@app.route('/retirada/criar', methods=['POST'])
def criar_pedido_retirada():
    if not verificar_login():
        return redirect(url_for('login'))
    
    cliente_nome = request.form['cliente_nome']
    cliente_telefone = request.form['cliente_telefone']
    itens = request.form.getlist('itens')
    
    if not itens:
        flash('Adicione pelo menos um item ao pedido!', 'error')
        return redirect(url_for('retirada'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Criar pedido
    cursor.execute('''
        INSERT INTO pedidos (tipo, usuario_id, cliente_nome, cliente_telefone)
        VALUES (?, ?, ?, ?)
    ''', ('retirada', session['user_id'], cliente_nome, cliente_telefone))
    
    pedido_id = cursor.lastrowid
    total = 0
    
    # Processar itens (simplificado para exemplo)
    for item_data in itens:
        # Aqui você processaria cada item do JSON
        # Por simplicidade, vou assumir um formato básico
        pass
    
    # Atualizar total e finalizar
    cursor.execute('UPDATE pedidos SET total = ?, status = "finalizado" WHERE id = ?', (total, pedido_id))
    
    conn.commit()
    conn.close()
    
    # Gerar link WhatsApp
    mensagem = f"🍕 *NOVO PEDIDO - RETIRADA*\n"
    mensagem += f"📋 Pedido: #{pedido_id}\n"
    mensagem += f"👤 Cliente: {cliente_nome}\n"
    mensagem += f"📞 Telefone: {cliente_telefone}\n"
    mensagem += f"💰 Total: R$ {total:.2f}\n"
    mensagem += f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    
    whatsapp_link = f"https://wa.me/5511999999999?text={urllib.parse.quote(mensagem)}"
    
    flash('Pedido criado! Enviando para o WhatsApp...', 'success')
    return redirect(whatsapp_link)

# Relatórios
@app.route('/relatorios')
def relatorios():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    config = get_configuracoes()
    data_inicio = request.args.get('data_inicio', datetime.now().strftime('%Y-%m-%d'))
    data_fim = request.args.get('data_fim', datetime.now().strftime('%Y-%m-%d'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.id, p.tipo, p.cliente_nome, p.total, p.created_at,
               GROUP_CONCAT(ip.produto_nome || ' (' || ip.tamanho || ')') as itens
        FROM pedidos p
        LEFT JOIN itens_pedido ip ON p.id = ip.pedido_id
        WHERE DATE(p.created_at) BETWEEN ? AND ? AND p.status = 'fechado'
        GROUP BY p.id
        ORDER BY p.created_at DESC
    ''', (data_inicio, data_fim))
    
    vendas = cursor.fetchall()
    
    cursor.execute('''
        SELECT COALESCE(SUM(total), 0), COUNT(*)
        FROM pedidos
        WHERE DATE(created_at) BETWEEN ? AND ? AND status = 'fechado'
    ''', (data_inicio, data_fim))
    
    total_periodo, quantidade_pedidos = cursor.fetchone()
    
    conn.close()
    
    return render_template('relatorios.html',
                         config=config,
                         vendas=vendas, 
                         total_periodo=total_periodo,
                         quantidade_pedidos=quantidade_pedidos,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

# Usuários
@app.route('/usuarios')
def usuarios():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, tipo, ativo, created_at FROM usuarios ORDER BY created_at DESC')
    usuarios = cursor.fetchall()
    conn.close()
    
    return render_template('usuarios.html', usuarios=usuarios, config=config)

@app.route('/usuarios/adicionar', methods=['POST'])
def adicionar_usuario():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('usuarios'))
    
    username = request.form['username']
    password = hashlib.sha256(request.form['password'].encode()).hexdigest()
    tipo = request.form['tipo']
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO usuarios (username, password, tipo) VALUES (?, ?, ?)', 
                      (username, password, tipo))
        conn.commit()
        flash('Usuário adicionado com sucesso!', 'success')
    except sqlite3.IntegrityError:
        flash('Nome de usuário já existe!', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('usuarios'))

@app.route('/usuarios/toggle/<int:user_id>')
def toggle_usuario(user_id):
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('usuarios'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET ativo = NOT ativo WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    flash('Status do usuário alterado!', 'success')
    return redirect(url_for('usuarios'))

# API para buscar produtos
@app.route('/api/produtos/<int:categoria_id>')
def api_produtos(categoria_id):
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, nome, preco_p, preco_m, preco_g, preco_familia
        FROM produtos
        WHERE categoria_id = ? AND ativo = 1
    ''', (categoria_id,))
    produtos = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        'id': p[0],
        'nome': p[1],
        'preco_p': p[2],
        'preco_m': p[3],
        'preco_g': p[4],
        'preco_familia': p[5]
    } for p in produtos])

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)