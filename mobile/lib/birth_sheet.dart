import 'package:flutter/material.dart';
import 'api.dart';
import 'celestial_widgets.dart';
import 'l10n/app_localizations.dart';

class BirthSubmission {
  const BirthSubmission(this.details,
      {required this.adult,
      required this.parental,
      required this.partnerPermission});
  final Json details;
  final bool adult, parental, partnerPermission;
}

class BirthForm extends StatefulWidget {
  const BirthForm({super.key, this.initial, this.partner = false});
  final Json? initial;
  final bool partner;
  @override
  State<BirthForm> createState() => _BirthFormState();
}

class _BirthFormState extends State<BirthForm> {
  final _form = GlobalKey<FormState>();
  final _fields = <String, TextEditingController>{};
  bool dpdp = false, adult = false, parental = false, permission = false;
  bool married = false;
  String node = 'MEAN';
  @override
  void initState() {
    super.initState();
    for (final name in [
      'name',
      'birth_date',
      'birth_time',
      'place_name',
      'country',
      'latitude',
      'longitude',
      'timezone_override',
      'uncertainty_minutes'
    ]) {
      _fields[name] = TextEditingController(
          text: widget.initial?[name]?.toString() ??
              (name == 'uncertainty_minutes' ? '0' : ''));
    }
    node = widget.initial?['node_type']?.toString() ?? 'MEAN';
    married = widget.initial?['already_married'] == true;
  }

  @override
  void dispose() {
    for (final controller in _fields.values) {
      controller.dispose();
    }
    super.dispose();
  }

  String value(String name) => _fields[name]!.text.trim();
  bool validDate(String text) {
    if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text)) return false;
    final parsed = DateTime.tryParse(text);
    return parsed != null &&
        parsed.toIso8601String().startsWith(text) &&
        !parsed.isAfter(DateTime.now()) &&
        parsed.year >= 1800;
  }

  bool validTime(String text) =>
      RegExp(r'^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$').hasMatch(text);
  bool get validCoords {
    final a = value('latitude'), b = value('longitude');
    if (a.isEmpty && b.isEmpty) return true;
    final lat = double.tryParse(a), lon = double.tryParse(b);
    return lat != null &&
        lon != null &&
        lat.isFinite &&
        lon.isFinite &&
        lat >= -90 &&
        lat <= 90 &&
        lon >= -180 &&
        lon <= 180;
  }

  void submit() {
    if (!_form.currentState!.validate() ||
        !dpdp ||
        !(adult || parental) ||
        (widget.partner && !permission)) {
      return;
    }
    final details = <String, dynamic>{
      'name': value('name'),
      'birth_date': value('birth_date'),
      'birth_time': value('birth_time'),
      'place_name': value('place_name'),
      'country': value('country'),
      'uncertainty_minutes': int.parse(value('uncertainty_minutes')),
      'node_type': node,
      'language': Localizations.localeOf(context).languageCode,
      if (value('latitude').isNotEmpty)
        'latitude': double.parse(value('latitude')),
      if (value('longitude').isNotEmpty)
        'longitude': double.parse(value('longitude')),
      if (value('timezone_override').isNotEmpty)
        'timezone_override': value('timezone_override'),
      if (widget.partner) 'already_married': married,
    };
    Navigator.pop(
        context,
        BirthSubmission(details,
            adult: adult, parental: parental, partnerPermission: permission));
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    Widget field(String name, String label,
            {String? Function(String?)? validator,
            TextInputType? keyboard,
            Widget? suffix}) =>
        Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: TextFormField(
                key: Key(name),
                controller: _fields[name],
                keyboardType: keyboard,
                autocorrect: false,
                enableSuggestions: false,
                decoration:
                    InputDecoration(labelText: label, suffixIcon: suffix),
                validator: validator ??
                    (v) => v == null || v.trim().isEmpty
                        ? t.requiredField
                        : null));
    return Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(t.birthIntro, style: const TextStyle(color: muted, height: 1.5)),
          const SizedBox(height: 20),
          field('name', t.nameLabel),
          field('birth_date', t.dateLabel,
              keyboard: TextInputType.datetime,
              validator: (v) =>
                  validDate(v?.trim() ?? '') ? null : t.invalidDate,
              suffix: IconButton(
                  tooltip: t.dateLabel,
                  icon: const Icon(Icons.calendar_month_outlined, size: 20),
                  onPressed: () async {
                    final date = await showDatePicker(
                        context: context,
                        firstDate: DateTime(1800),
                        lastDate: DateTime.now(),
                        initialDate: DateTime.tryParse(value('birth_date')) ??
                            DateTime.now());
                    if (date != null && mounted) {
                      _fields['birth_date']!.text =
                          date.toIso8601String().substring(0, 10);
                    }
                  })),
          field('birth_time', t.timeLabel,
              keyboard: TextInputType.datetime,
              validator: (v) =>
                  validTime(v?.trim() ?? '') ? null : t.invalidTime,
              suffix: IconButton(
                  tooltip: t.timeLabel,
                  icon: const Icon(Icons.schedule, size: 20),
                  onPressed: () async {
                    final time = await showTimePicker(
                        context: context,
                        initialTime: TimeOfDay.now(),
                        builder: (context, child) => MediaQuery(
                            data: MediaQuery.of(context)
                                .copyWith(alwaysUse24HourFormat: true),
                            child: child!));
                    if (time != null && mounted) {
                      _fields['birth_time']!.text =
                          '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
                    }
                  })),
          field('place_name', t.placeLabel,
              validator: (v) =>
                  (v?.trim().length ?? 0) >= 2 ? null : t.requiredField),
          field('country', t.countryLabel,
              validator: (v) =>
                  (v?.trim().length ?? 0) >= 2 ? null : t.requiredField),
          Text(t.coordinatesHint,
              style: const TextStyle(color: muted, fontSize: 12, height: 1.5)),
          const SizedBox(height: 12),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
                child: field('latitude', t.latitudeLabel,
                    keyboard: const TextInputType.numberWithOptions(
                        decimal: true, signed: true),
                    validator: (_) =>
                        validCoords ? null : t.invalidCoordinates)),
            const SizedBox(width: 10),
            Expanded(
                child: field('longitude', t.longitudeLabel,
                    keyboard: const TextInputType.numberWithOptions(
                        decimal: true, signed: true),
                    validator: (_) =>
                        validCoords ? null : t.invalidCoordinates)),
          ]),
          field('timezone_override', t.timezoneLabel, validator: (_) => null),
          field('uncertainty_minutes', t.uncertaintyLabel,
              keyboard: TextInputType.number, validator: (v) {
            final n = int.tryParse(v ?? '');
            return n != null && n >= 0 && n <= 120 ? null : t.requiredField;
          }),
          DropdownButtonFormField<String>(
              initialValue: node,
              decoration: InputDecoration(labelText: t.nodeLabel),
              items: [
                DropdownMenuItem(value: 'MEAN', child: Text(t.meanNode)),
                DropdownMenuItem(value: 'TRUE', child: Text(t.trueNode))
              ],
              onChanged: (v) => setState(() => node = v!)),
          const SizedBox(height: 16),
          CheckboxListTile(
              key: const Key('dpdp_consent'),
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              value: dpdp,
              title: Text(t.dpdpConsent, style: const TextStyle(fontSize: 13)),
              onChanged: (v) => setState(() => dpdp = v!)),
          CheckboxListTile(
              key: const Key('adult_consent'),
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              value: adult,
              title: Text(t.adultConsent, style: const TextStyle(fontSize: 13)),
              onChanged: (v) => setState(() {
                    adult = v!;
                    if (adult) parental = false;
                  })),
          CheckboxListTile(
              key: const Key('parental_consent'),
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              value: parental,
              title:
                  Text(t.parentalConsent, style: const TextStyle(fontSize: 13)),
              onChanged: (v) => setState(() {
                    parental = v!;
                    if (parental) adult = false;
                  })),
          if (widget.partner) ...[
            CheckboxListTile(
                key: const Key('partner_consent'),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                value: permission,
                title: Text(t.partnerConsent,
                    style: const TextStyle(fontSize: 13)),
                onChanged: (v) => setState(() => permission = v!)),
            CheckboxListTile(
                key: const Key('already_married'),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                value: married,
                title: Text(t.alreadyMarried,
                    style: const TextStyle(fontSize: 13)),
                onChanged: (v) => setState(() => married = v!)),
          ],
          const SizedBox(height: 10),
          Text(t.sessionPrivacy,
              style: const TextStyle(color: muted, fontSize: 12, height: 1.5)),
          const SizedBox(height: 20),
          SizedBox(
              width: double.infinity,
              child: FilledButton(
                  key: const Key('calculate_chart'),
                  onPressed: dpdp &&
                          (adult || parental) &&
                          (!widget.partner || permission)
                      ? submit
                      : null,
                  child: Text(
                      widget.partner ? t.calculateMatch : t.calculateChart))),
        ]));
  }
}
