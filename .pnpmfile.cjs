function readPackage(pkg) {
  if (pkg.dependencies && pkg.dependencies.nanoid) {
    if (pkg.dependencies.nanoid.startsWith('3.') || pkg.dependencies.nanoid.startsWith('^3.')) {
      pkg.dependencies.nanoid = '^3.3.18';
    }
  }
  return pkg;
}

module.exports = {
  hooks: {
    readPackage,
  },
};
