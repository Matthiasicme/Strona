from flask import Blueprint, jsonify, request, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from models.termin import Termin
from models.lekarz import Lekarz
from models.usluga import Usluga
from models.wizyta import Wizyta
from app import db

termin_bp = Blueprint('termin', __name__, url_prefix='/termin')

@termin_bp.route('/kalendarz')
def kalendarz():
    return render_template('kalendarz.html')

@termin_bp.route('/dostepne')
@login_required
def dostepne_terminy():
    data = request.args.get('data')
    lekarz_id = request.args.get('lekarz_id', type=int)
    
    if not data:
        return jsonify({'error': 'Brak wymaganych parametrów'}), 400
    
    try:
        data = datetime.strptime(data, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Nieprawidłowy format daty'}), 400
    
    # Pobierz godziny pracy lekarza (tutaj uproszczone - można dodać model z godzinami pracy)
    godziny_pracy = [
        time(9, 0), time(10, 0), time(11, 0), 
        time(12, 0), time(13, 0), time(14, 0), 
        time(15, 0), time(16, 0)
    ]
    
    # Pobierz zajęte terminy
    zajete_terminy = db.session.query(Termin.godzina_od, Termin.godzina_do).\
        join(Wizyta).\
        filter(
            Termin.data == data,
            Termin.lekarz_id == lekarz_id,
            Wizyta.status.in_(['ZAPLANOWANA', 'POTWIERDZONA'])
        ).all()
    
    zajete_godziny = [t[0].strftime('%H:%M') for t in zajete_terminy]
    
    # Filtruj dostępne godziny
    dostepne_godziny = [
        godzina.strftime('%H:%M') 
        for godzina in godziny_pracy 
        if godzina.strftime('%H:%M') not in zajete_godziny
    ]
    
    return jsonify({
        'data': data.strftime('%Y-%m-%d'),
        'dostepne_godziny': dostepne_godziny
    })

@termin_bp.route('/zapisz', methods=['POST'])
@login_required
def zapisz_na_wizyte():
    data = request.form.get('data')
    godzina = request.form.get('godzina')
    lekarz_id = request.form.get('lekarz_id')
    usluga_id = request.form.get('usluga_id')
    
    if not all([data, godzina, lekarz_id, usluga_id]):
        flash('Wypełnij wszystkie wymagane pola', 'error')
        return redirect(url_for('termin.kalendarz'))
    
    try:
        data_obj = datetime.strptime(data, '%Y-%m-%d').date()
        godzina_obj = datetime.strptime(godzina, '%H:%M').time()
        
        # Sprawdź czy termin jest dostępny
        termin = Termin.query.filter_by(
            data=data_obj,
            godzina_od=godzina_obj,
            lekarz_id=lekarz_id,
            dostepny=True
        ).first()
        
        if not termin:
            # Utwórz nowy termin
            termin = Termin(
                data=data_obj,
                godzina_od=godzina_obj,
                godzina_do=(datetime.combine(data_obj, godzina_obj) + timedelta(minutes=30)).time(),
                lekarz_id=lekarz_id,
                dostepny=True
            )
            db.session.add(termin)
            db.session.flush()  # Pobierz ID nowego terminu
        
        # Utwórz wizytę
        wizyta = Wizyta(
            pacjent_id=current_user.id,
            lekarz_id=lekarz_id,
            termin_id=termin.id,
            status='ZAPLANOWANA',
            opis=f'Wizyta kontrolna - {usluga_id}'
        )
        
        db.session.add(wizyta)
        db.session.commit()
        
        flash('Wizyta została zarejestrowana pomyślnie!', 'success')
        return redirect(url_for('termin.moje_wizyty'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Wystąpił błąd podczas rejestracji wizyty: {str(e)}', 'error')
        return redirect(url_for('termin.kalendarz'))

@termin_bp.route('/moje-wizyty')
@login_required
def moje_wizyty():
    wizyty = Wizyta.query.filter_by(pacjent_id=current_user.id).order_by(Termin.data.desc(), Termin.godzina_od.desc()).all()
    return render_template('moje_wizyty.html', wizyty=wizyty)
