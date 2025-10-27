from flask import Blueprint, render_template, current_app

site_bp = Blueprint('site', __name__, url_prefix='/site')

@site_bp.route('/<id>')
def site_detail(id):
    doc_ref = current_app.db.collection(u'stations').document(id)
    site = doc_ref.get()
    if not site.exists:
        return "Site not found", 404
    site = site.to_dict()
    if site['deleted']:
        return "Site not found", 404

    date_increment = site.get('date_increment', 'bimonthly')
    labels, current_index, _ = current_app.generate_labels_and_current_index(date_increment)

    counts_to_render = []
    for i in range(len(labels)):
        if i <= current_index:
            counts_to_render.append(site['counts'][i] if i < len(site['counts']) else 0)
        else:
            counts_to_render.append(None)

    return render_template('site_detail.html', 
                           site=site, 
                           labels=labels, 
                           counts=counts_to_render,
                           current_index=current_index,
                           id=id
                          )

@site_bp.route('/<id>/comments')
def site_comments(id):
    doc_ref = current_app.db.collection(u'stations').document(id)
    site = doc_ref.get()
    if not site.exists:
        return "Site not found", 404
    site = site.to_dict()
    if site['deleted']:
        return "Site not found", 404
    return render_template('site_comments.html', site=site, id=id)
