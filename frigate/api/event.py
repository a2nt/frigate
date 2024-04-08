"""Event apis."""

import logging
import os
from datetime import datetime
from functools import reduce
from pathlib import Path
from urllib.parse import unquote

import cv2
from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    request,
)
from peewee import DoesNotExist, fn, operator
from playhouse.shortcuts import model_to_dict

from frigate.const import (
    CLIPS_DIR,
)
from frigate.models import Event, Timeline
from frigate.object_processing import TrackedObject
from frigate.util.builtin import get_tz_modifiers

logger = logging.getLogger(__name__)

EventBp = Blueprint("events", __name__)

DEFAULT_TIME_RANGE = "00:00,24:00"


@EventBp.route("/events")
def events():
    camera = request.args.get("camera", "all")
    cameras = request.args.get("cameras", "all")

    # handle old camera arg
    if cameras == "all" and camera != "all":
        cameras = camera

    label = unquote(request.args.get("label", "all"))
    labels = request.args.get("labels", "all")

    # handle old label arg
    if labels == "all" and label != "all":
        labels = label

    sub_label = request.args.get("sub_label", "all")
    sub_labels = request.args.get("sub_labels", "all")

    # handle old sub_label arg
    if sub_labels == "all" and sub_label != "all":
        sub_labels = sub_label

    zone = request.args.get("zone", "all")
    zones = request.args.get("zones", "all")

    # handle old label arg
    if zones == "all" and zone != "all":
        zones = zone

    limit = request.args.get("limit", 100)
    after = request.args.get("after", type=float)
    before = request.args.get("before", type=float)
    time_range = request.args.get("time_range", DEFAULT_TIME_RANGE)
    has_clip = request.args.get("has_clip", type=int)
    has_snapshot = request.args.get("has_snapshot", type=int)
    in_progress = request.args.get("in_progress", type=int)
    include_thumbnails = request.args.get("include_thumbnails", default=1, type=int)
    favorites = request.args.get("favorites", type=int)
    min_score = request.args.get("min_score", type=float)
    max_score = request.args.get("max_score", type=float)
    min_length = request.args.get("min_length", type=float)
    max_length = request.args.get("max_length", type=float)

    clauses = []

    selected_columns = [
        Event.id,
        Event.camera,
        Event.label,
        Event.zones,
        Event.start_time,
        Event.end_time,
        Event.has_clip,
        Event.has_snapshot,
        Event.retain_indefinitely,
        Event.sub_label,
        Event.top_score,
        Event.box,
        Event.data,
    ]

    if camera != "all":
        clauses.append((Event.camera == camera))

    if cameras != "all":
        camera_list = cameras.split(",")
        clauses.append((Event.camera << camera_list))

    if labels != "all":
        label_list = labels.split(",")
        clauses.append((Event.label << label_list))

    if sub_labels != "all":
        # use matching so joined sub labels are included
        # for example a sub label 'bob' would get events
        # with sub labels 'bob' and 'bob, john'
        sub_label_clauses = []
        filtered_sub_labels = sub_labels.split(",")

        if "None" in filtered_sub_labels:
            filtered_sub_labels.remove("None")
            sub_label_clauses.append((Event.sub_label.is_null()))

        for label in filtered_sub_labels:
            sub_label_clauses.append(
                (Event.sub_label.cast("text") == label)
            )  # include exact matches

            # include this label when part of a list
            sub_label_clauses.append((Event.sub_label.cast("text") % f"*{label},*"))
            sub_label_clauses.append((Event.sub_label.cast("text") % f"*, {label}*"))

        sub_label_clause = reduce(operator.or_, sub_label_clauses)
        clauses.append((sub_label_clause))

    if zones != "all":
        # use matching so events with multiple zones
        # still match on a search where any zone matches
        zone_clauses = []
        filtered_zones = zones.split(",")

        if "None" in filtered_zones:
            filtered_zones.remove("None")
            zone_clauses.append((Event.zones.length() == 0))

        for zone in filtered_zones:
            zone_clauses.append((Event.zones.cast("text") % f'*"{zone}"*'))

        zone_clause = reduce(operator.or_, zone_clauses)
        clauses.append((zone_clause))

    if after:
        clauses.append((Event.start_time > after))

    if before:
        clauses.append((Event.start_time < before))

    if time_range != DEFAULT_TIME_RANGE:
        # get timezone arg to ensure browser times are used
        tz_name = request.args.get("timezone", default="utc", type=str)
        hour_modifier, minute_modifier, _ = get_tz_modifiers(tz_name)

        times = time_range.split(",")
        time_after = times[0]
        time_before = times[1]

        start_hour_fun = fn.strftime(
            "%H:%M",
            fn.datetime(Event.start_time, "unixepoch", hour_modifier, minute_modifier),
        )

        # cases where user wants events overnight, ex: from 20:00 to 06:00
        # should use or operator
        if time_after > time_before:
            clauses.append(
                (
                    reduce(
                        operator.or_,
                        [(start_hour_fun > time_after), (start_hour_fun < time_before)],
                    )
                )
            )
        # all other cases should be and operator
        else:
            clauses.append((start_hour_fun > time_after))
            clauses.append((start_hour_fun < time_before))

    if has_clip is not None:
        clauses.append((Event.has_clip == has_clip))

    if has_snapshot is not None:
        clauses.append((Event.has_snapshot == has_snapshot))

    if in_progress is not None:
        clauses.append((Event.end_time.is_null(in_progress)))

    if include_thumbnails:
        selected_columns.append(Event.thumbnail)

    if favorites:
        clauses.append((Event.retain_indefinitely == favorites))

    if max_score is not None:
        clauses.append((Event.data["score"] <= max_score))

    if min_score is not None:
        clauses.append((Event.data["score"] >= min_score))

    if min_length is not None:
        clauses.append(((Event.end_time - Event.start_time) >= min_length))

    if max_length is not None:
        clauses.append(((Event.end_time - Event.start_time) <= max_length))

    if len(clauses) == 0:
        clauses.append((True))

    events = (
        Event.select(*selected_columns)
        .where(reduce(operator.and_, clauses))
        .order_by(Event.start_time.desc())
        .limit(limit)
        .dicts()
        .iterator()
    )

    return jsonify(list(events))


@EventBp.route("/events/summary")
def events_summary():
    tz_name = request.args.get("timezone", default="utc", type=str)
    hour_modifier, minute_modifier, seconds_offset = get_tz_modifiers(tz_name)
    has_clip = request.args.get("has_clip", type=int)
    has_snapshot = request.args.get("has_snapshot", type=int)

    clauses = []

    if has_clip is not None:
        clauses.append((Event.has_clip == has_clip))

    if has_snapshot is not None:
        clauses.append((Event.has_snapshot == has_snapshot))

    if len(clauses) == 0:
        clauses.append((True))

    groups = (
        Event.select(
            Event.camera,
            Event.label,
            Event.sub_label,
            fn.strftime(
                "%Y-%m-%d",
                fn.datetime(
                    Event.start_time, "unixepoch", hour_modifier, minute_modifier
                ),
            ).alias("day"),
            Event.zones,
            fn.COUNT(Event.id).alias("count"),
        )
        .where(reduce(operator.and_, clauses))
        .group_by(
            Event.camera,
            Event.label,
            Event.sub_label,
            (Event.start_time + seconds_offset).cast("int") / (3600 * 24),
            Event.zones,
        )
    )

    return jsonify([e for e in groups.dicts()])


@EventBp.route("/events/<id>", methods=("GET",))
def event(id):
    try:
        return model_to_dict(Event.get(Event.id == id))
    except DoesNotExist:
        return "Event not found", 404


@EventBp.route("/events/<id>/retain", methods=("POST",))
def set_retain(id):
    try:
        event = Event.get(Event.id == id)
    except DoesNotExist:
        return make_response(
            jsonify({"success": False, "message": "Event " + id + " not found"}), 404
        )

    event.retain_indefinitely = True
    event.save()

    return make_response(
        jsonify({"success": True, "message": "Event " + id + " retained"}), 200
    )

@EventBp.route("/events/<id>/retain", methods=("DELETE",))
def delete_retain(id):
    try:
        event = Event.get(Event.id == id)
    except DoesNotExist:
        return make_response(
            jsonify({"success": False, "message": "Event " + id + " not found"}), 404
        )

    event.retain_indefinitely = False
    event.save()

    return make_response(
        jsonify({"success": True, "message": "Event " + id + " un-retained"}), 200
    )


@EventBp.route("/events/<id>/sub_label", methods=("POST",))
def set_sub_label(id):
    try:
        event: Event = Event.get(Event.id == id)
    except DoesNotExist:
        return make_response(
            jsonify({"success": False, "message": "Event " + id + " not found"}), 404
        )

    json: dict[str, any] = request.get_json(silent=True) or {}
    new_sub_label = json.get("subLabel")
    new_score = json.get("subLabelScore")

    if new_sub_label is None:
        return make_response(
            jsonify(
                {
                    "success": False,
                    "message": "A sub label must be supplied",
                }
            ),
            400,
        )

    if new_sub_label and len(new_sub_label) > 100:
        return make_response(
            jsonify(
                {
                    "success": False,
                    "message": new_sub_label
                    + " exceeds the 100 character limit for sub_label",
                }
            ),
            400,
        )

    if new_score is not None and (new_score > 1.0 or new_score < 0):
        return make_response(
            jsonify(
                {
                    "success": False,
                    "message": new_score
                    + " does not fit within the expected bounds 0 <= score <= 1.0",
                }
            ),
            400,
        )

    if not event.end_time:
        # update tracked object
        tracked_obj: TrackedObject = (
            current_app.detected_frames_processor.camera_states[
                event.camera
            ].tracked_objects.get(event.id)
        )

        if tracked_obj:
            tracked_obj.obj_data["sub_label"] = (new_sub_label, new_score)

        # update timeline items
        Timeline.update(
            data=Timeline.data.update({"sub_label": (new_sub_label, new_score)})
        ).where(Timeline.source_id == id).execute()

    event.sub_label = new_sub_label

    if new_score:
        data = event.data
        data["sub_label_score"] = new_score
        event.data = data

    event.save()
    return make_response(
        jsonify(
            {
                "success": True,
                "message": "Event " + id + " sub label set to " + new_sub_label,
            }
        ),
        200,
    )


@EventBp.route("/events/<id>", methods=("DELETE",))
def delete_event(id):
    try:
        event = Event.get(Event.id == id)
    except DoesNotExist:
        return make_response(
            jsonify({"success": False, "message": "Event " + id + " not found"}), 404
        )

    media_name = f"{event.camera}-{event.id}"
    if event.has_snapshot:
        media = Path(f"{os.path.join(CLIPS_DIR, media_name)}.jpg")
        media.unlink(missing_ok=True)
        media = Path(f"{os.path.join(CLIPS_DIR, media_name)}-clean.png")
        media.unlink(missing_ok=True)
    if event.has_clip:
        media = Path(f"{os.path.join(CLIPS_DIR, media_name)}.mp4")
        media.unlink(missing_ok=True)

    event.delete_instance()
    Timeline.delete().where(Timeline.source_id == id).execute()
    return make_response(
        jsonify({"success": True, "message": "Event " + id + " deleted"}), 200
    )


@EventBp.route("/events/<camera_name>/<label>/create", methods=["POST"])
def create_event(camera_name, label):
    if not camera_name or not current_app.frigate_config.cameras.get(camera_name):
        return make_response(
            jsonify(
                {"success": False, "message": f"{camera_name} is not a valid camera."}
            ),
            404,
        )

    if not label:
        return make_response(
            jsonify({"success": False, "message": f"{label} must be set."}), 404
        )

    json: dict[str, any] = request.get_json(silent=True) or {}

    try:
        frame = current_app.detected_frames_processor.get_current_frame(camera_name)

        event_id = current_app.external_processor.create_manual_event(
            camera_name,
            label,
            json.get("source_type", "api"),
            json.get("sub_label", None),
            json.get("score", 0),
            json.get("duration", 30),
            json.get("include_recording", True),
            json.get("draw", {}),
            frame,
        )
    except Exception as e:
        logger.error(e)
        return make_response(
            jsonify({"success": False, "message": "An unknown error occurred"}),
            500,
        )

    return make_response(
        jsonify(
            {
                "success": True,
                "message": "Successfully created event.",
                "event_id": event_id,
            }
        ),
        200,
    )


@EventBp.route("/events/<event_id>/end", methods=["PUT"])
def end_event(event_id):
    json: dict[str, any] = request.get_json(silent=True) or {}

    try:
        end_time = json.get("end_time", datetime.now().timestamp())
        current_app.external_processor.finish_manual_event(event_id, end_time)
    except Exception:
        return make_response(
            jsonify(
                {"success": False, "message": f"{event_id} must be set and valid."}
            ),
            404,
        )

    return make_response(
        jsonify({"success": True, "message": "Event successfully ended."}), 200
    )
