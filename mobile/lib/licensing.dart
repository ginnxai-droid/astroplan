/// AGPL-3.0 network-use source offer. Kept local so it is reachable offline.
const String _configuredSourceOffer = String.fromEnvironment(
  'ASTRO_SOURCE_OFFER_URL',
);
const String kSourceOfferUrl = _configuredSourceOffer == ''
    ? 'https://github.com/ginnxai-droid/astroplan'
    : _configuredSourceOffer;
const String kSourceOfferLicense = 'AGPL-3.0';
