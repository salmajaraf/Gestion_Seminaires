from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from app.models import db, Reservation
import requests
from app.services import trouver_dates_possibles, Confirmation_email, new_date_email, verify_token

bp = Blueprint('reservations', __name__)

@bp.route("/")
def home():
    return "Bienvenue dans le service de réservation !", 200

@bp.route('/reservation-service/create-reservation', methods=['POST'])
def creer_reservation():
    # Récupérer les données JSON envoyées dans le corps de la requête
    data = request.get_json()

    # Extraire les paramètres du JSON payload
    utilisateur_id = data.get('utilisateur_id')
    seminaire_id = data.get('seminaire_id')
    date_debut_str = data.get('date')  # Format ISO8601 attendu
    duree = data.get('duree', 1)  # Par défaut, durée = 1 heure

    if not utilisateur_id or not seminaire_id or not date_debut_str:
        return {"error": "Paramètres manquants : 'utilisateur_id', 'seminaire_id', 'date' sont obligatoires."}, 400

    try:
        # Convertir la date de début depuis le format ISO 8601
        date_debut = datetime.fromisoformat(date_debut_str)
    except ValueError:
        return {"error": "Format de date invalide. Utilisez ISO 8601 (ex : '2024-12-02T10:00:00')"}, 400

    # Calculer la date de fin
    date_fin = date_debut + timedelta(hours=duree)

    # Vérifier si la date est disponible
    conflit = Reservation.query.filter(
        (Reservation.date_debut < date_fin) & (Reservation.date_fin > date_debut)
    ).first()

    if conflit:
        # Trouver des dates possibles si la réservation entre en conflit
        dates_possibles = trouver_dates_possibles(date_debut, duree, seminaire_id)

        if dates_possibles:
            # Récupérer la première date possible
            premier_reservation = dates_possibles[0]['periodes'][0]
            date_debut_str = premier_reservation['entre']
            jour_date = datetime.strptime(dates_possibles[0]['jour'], '%Y-%m-%d').date()
            heure_debut = datetime.strptime(date_debut_str, '%H:%M').time()
            date_debut = datetime.combine(jour_date, heure_debut)
            date_fin = date_debut + timedelta(hours=duree)

            # Créer un message pour notifier l'utilisateur
            message = {
                "message": (
                    f"La date demandée n'était pas disponible. La réservation a été déplacée à : "
                    f"{date_debut.strftime('%Y-%m-%d %H:%M:%S')}."
                ),
                "dates_possibles": dates_possibles
            }

            # Envoyer un e-mail de proposition
            new_date_email(utilisateur_id, seminaire_id, date_debut, dates_possibles)

        else:
            # Aucun créneau disponible
            return {"error": "Aucun créneau disponible pour la réservation."}, 409
    else:
        # Si aucune réservation en conflit, créer la réservation
        message = {
            "message": f"Réservation créée avec succès pour le {date_debut.strftime('%Y-%m-%d %H:%M:%S')}."
        }
        Confirmation_email(utilisateur_id, seminaire_id, date_debut)

    # Créer et sauvegarder la réservation
    reservation = Reservation(
        utilisateur_id=utilisateur_id,
        seminaire_id=seminaire_id,
        date_debut=date_debut,
        date_fin=date_fin
    )
    db.session.add(reservation)
    db.session.commit()

    # Retourner un message de succès
    return message, 201


@bp.route('/reservation-service/update-reservation/<int:seminaire_id>', methods=['PUT'])
def modifier_reservation(seminaire_id):
    print('called')
    """Mettre à jour une réservation existante."""
    data = request.get_json()  
    utilisateur_existe = verify_token(data.get('token'))
    print('user',utilisateur_existe)
    
    # Récupérer le payload JSON envoyé par le client
    print(data)

    # Vérifier si la réservation existe
    reservation = Reservation.query.filter_by(seminaire_id=seminaire_id).first()

    if not reservation:
        return jsonify({"message": "Réservation non trouvée."}), 404

    # Mettre à jour 'date' si présent dans les données
    if 'date' in data:
        reservation.date_debut = datetime.strptime(data['date'], '%Y-%m-%d %H:%M:%S')
        reservation.date_fin = reservation.date_debut + timedelta(hours=int(data.get('duree', 1)))

    # Mettre à jour 'statut' si présent dans les données
    if 'statut' in data:
        reservation.statut = data.get('statut')

    # Enregistrer les modifications
    db.session.commit()
    return jsonify({"message": "Réservation mise à jour avec succès."})


@bp.route('/reservation-service/remove-reservation/<int:seminaire_id>', methods=['DELETE'])
def supprimer_reservation(seminaire_id):
    """Supprimer une réservation."""
    reservation = Reservation.query.filter_by(seminaire_id=seminaire_id).first()

    if not reservation:
        return jsonify({"message": "Réservation non trouvée."}), 404

    db.session.delete(reservation)
    db.session.commit()
    return jsonify({"message": "Réservation supprimée avec succès."})
