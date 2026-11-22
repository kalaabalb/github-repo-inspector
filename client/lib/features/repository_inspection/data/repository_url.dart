/// A validated GitHub repository reference.
///
/// Accepts the ways people actually paste repositories: full links, links
/// with `/tree/main`, `/blob/...`, `.git` or a trailing slash, `www.github.com`,
/// links without a scheme, and the `owner/repo` shorthand.
class RepositoryUrl {
  const RepositoryUrl(this.owner, this.repo);

  final String owner;
  final String repo;

  String get fullName => '$owner/$repo';
  String get url => 'https://github.com/$owner/$repo';

  static final _shorthand = RegExp(r'^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$');
  static final _identifier = RegExp(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$');

  static RepositoryUrl? tryParse(String input) {
    var value = input.trim();
    if (value.isEmpty) return null;
    if (_shorthand.hasMatch(value)) {
      value = 'https://github.com/$value';
    } else if (!value.contains('://')) {
      value = 'https://$value';
    }
    final uri = Uri.tryParse(value);
    if (uri == null) return null;
    if (uri.scheme != 'https' && uri.scheme != 'http') return null;
    final host = uri.host.toLowerCase();
    if (host != 'github.com' && host != 'www.github.com') return null;
    final parts = uri.pathSegments.where((part) => part.isNotEmpty).toList();
    if (parts.length < 2) return null;
    final owner = parts[0];
    var repo = parts[1];
    if (repo.endsWith('.git')) {
      repo = repo.substring(0, repo.length - 4);
    }
    if (!_identifier.hasMatch(owner) || !_identifier.hasMatch(repo)) {
      return null;
    }
    return RepositoryUrl(owner, repo);
  }
}
